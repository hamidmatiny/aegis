package store_test

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"testing"
	"time"

	"github.com/google/uuid"
	_ "github.com/jackc/pgx/v5/stdlib"

	"github.com/aegis-platform/aegis/audit/internal/models"
	"github.com/aegis-platform/aegis/audit/internal/signer"
	"github.com/aegis-platform/aegis/audit/internal/store"
)

const testDevSigningSeed = "YWVnaXMtZGV2LWF1ZGl0LXNpZ25pbmcta2V5LXYxISE="

func openPostgresStore(t *testing.T) *store.PostgresStore {
	t.Helper()
	url := os.Getenv("DATABASE_URL")
	if url == "" {
		url = "postgres://aegis:aegis_dev@localhost:5432/aegis?sslmode=disable"
	}
	st, err := store.NewPostgresStore(url)
	if err != nil {
		t.Skipf("postgres unavailable: %v", err)
	}
	t.Cleanup(func() { _ = st.Close() })
	return st
}

func TestPostgresWriteGetVerifyUntouched(t *testing.T) {
	st := openPostgresStore(t)
	sg, err := signer.New("postgres-verify-test", testDevSigningSeed)
	if err != nil {
		t.Fatal(err)
	}

	receipt := models.Receipt{
		ReceiptID:    uuid.NewString(),
		EventType:    models.EventInputDefense,
		TenantID:     "verify-test",
		Trace:        &models.TraceContext{TraceID: "pg-roundtrip", RequestID: "req-1"},
		InputVerdict: json.RawMessage(`{"action":"BLOCK","fused_score":0.88}`),
		CreatedAt:    time.Now().UTC().Truncate(time.Microsecond),
	}
	if err := sg.SignReceipt(&receipt); err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	if err := st.Insert(ctx, &receipt); err != nil {
		t.Fatal(err)
	}

	loaded, err := st.Get(ctx, receipt.ReceiptID)
	if err != nil {
		t.Fatal(err)
	}

	valid, reason := sg.VerifyReceipt(loaded)
	if !valid {
		t.Fatalf("expected untouched postgres receipt to verify: %s", reason)
	}
}

func TestPostgresVerifyDetectsTamperedPayload(t *testing.T) {
	st := openPostgresStore(t)
	sg, err := signer.New("postgres-tamper-test", testDevSigningSeed)
	if err != nil {
		t.Fatal(err)
	}

	receipt := models.Receipt{
		ReceiptID:    uuid.NewString(),
		EventType:    models.EventInputDefense,
		TenantID:     "tamper-test",
		InputVerdict: json.RawMessage(`{"action":"BLOCK","fused_score":0.88}`),
		CreatedAt:    time.Now().UTC().Truncate(time.Microsecond),
	}
	if err := sg.SignReceipt(&receipt); err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	if err := st.Insert(ctx, &receipt); err != nil {
		t.Fatal(err)
	}

	url := os.Getenv("DATABASE_URL")
	if url == "" {
		url = "postgres://aegis:aegis_dev@localhost:5432/aegis?sslmode=disable"
	}
	db, err := sql.Open("pgx", url)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	_, err = db.ExecContext(ctx, `
		UPDATE audit_receipts
		SET payload = jsonb_set(payload, '{input_verdict,action}', '"ALLOW"')
		WHERE receipt_id = $1
	`, receipt.ReceiptID)
	if err != nil {
		t.Fatal(err)
	}

	loaded, err := st.Get(ctx, receipt.ReceiptID)
	if err != nil {
		t.Fatal(err)
	}

	valid, reason := sg.VerifyReceipt(loaded)
	if valid {
		t.Fatal("expected tampered postgres receipt to fail verification")
	}
	if reason != "payload hash mismatch (tampered)" {
		t.Fatalf("expected tamper reason, got %q", reason)
	}
}
