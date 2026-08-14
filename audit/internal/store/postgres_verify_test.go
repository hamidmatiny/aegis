package store_test

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
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
	sg, err := signer.New("postgres-verify-test", testDevSigningSeed, nil)
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
	sg, err := signer.New("postgres-tamper-test", testDevSigningSeed, nil)
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

// TestPostgresQueryPaginationDoesNotDropOrDuplicateAcrossPages is the
// real-database counterpart to store_test's memory-store version of this
// test -- it exercises the actual SQL Query() builds (the composite
// "(created_at, receipt_id) > ($n, $n+1)" row comparison and the
// LIMIT-plus-one/cursor derivation), not just the in-memory Go logic.
// Skipped like the other Postgres tests if no database is reachable --
// run it locally against `docker compose up -d postgres` (or CI's own
// integration job, which does have a real database) before trusting a
// change to postgres.go's Query().
func TestPostgresQueryPaginationDoesNotDropOrDuplicateAcrossPages(t *testing.T) {
	st := openPostgresStore(t)
	sg, err := signer.New("postgres-pagination-test", testDevSigningSeed, nil)
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	tenantID := "pagination-test-" + uuid.NewString()
	const n = 25
	base := time.Now().UTC().Truncate(time.Microsecond)
	want := make([]string, 0, n)
	for i := 0; i < n; i++ {
		// receipt_id deliberately the REVERSE of created_at order -- the
		// exact shape that broke the old single-column, wrong-row cursor.
		id := fmt.Sprintf("%s-%03d", uuid.NewString(), n-i)
		receipt := models.Receipt{
			ReceiptID:    id,
			EventType:    models.EventInputDefense,
			TenantID:     tenantID,
			InputVerdict: json.RawMessage(`{"action":"BLOCK","fused_score":0.9}`),
			CreatedAt:    base.Add(time.Duration(i) * time.Second),
		}
		if err := sg.SignReceipt(&receipt); err != nil {
			t.Fatal(err)
		}
		if err := st.Insert(ctx, &receipt); err != nil {
			t.Fatalf("insert %d: %v", i, err)
		}
		want = append(want, id)
	}

	var got []string
	cursor := ""
	pages := 0
	for {
		pages++
		if pages > n+2 {
			t.Fatal("too many pages -- pagination is likely looping")
		}
		resp, err := st.Query(ctx, models.QueryRequest{TenantID: tenantID, Limit: 4, Cursor: cursor})
		if err != nil {
			t.Fatalf("query page %d: %v", pages, err)
		}
		for _, r := range resp.Receipts {
			got = append(got, r.ReceiptID)
		}
		if resp.NextCursor == "" {
			break
		}
		cursor = resp.NextCursor
	}

	if len(got) != n {
		t.Fatalf("expected %d receipts across all pages, got %d", n, len(got))
	}
	seen := make(map[string]int, n)
	for _, id := range got {
		seen[id]++
	}
	for _, id := range want {
		if seen[id] != 1 {
			t.Errorf("receipt %q appeared %d times across pages (want exactly 1)", id, seen[id])
		}
	}
	for i := range got {
		if got[i] != want[i] {
			t.Fatalf("pagination order mismatch at index %d: got %q want %q", i, got[i], want[i])
		}
	}
}
