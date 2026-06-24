package service_test

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/aegis-platform/aegis/audit/internal/models"
	"github.com/aegis-platform/aegis/audit/internal/service"
	"github.com/aegis-platform/aegis/audit/internal/signer"
	"github.com/aegis-platform/aegis/audit/internal/store"
)

func newTestService(t *testing.T) *service.Service {
	t.Helper()
	sg, err := signer.GenerateDev("test")
	if err != nil {
		t.Fatal(err)
	}
	return service.New(store.NewMemoryStore(), sg)
}

func TestWriteQueryVerify(t *testing.T) {
	svc := newTestService(t)
	ctx := context.Background()

	writeResp, err := svc.Write(ctx, models.WriteReceiptRequest{
		EventType: models.EventInputDefense,
		TenantID:  "acme",
		Trace:     &models.TraceContext{TraceID: "t-1"},
		InputVerdict: json.RawMessage(`{"action":"BLOCK","fused_score":0.88}`),
		PolicyPackID: "default",
	})
	if err != nil {
		t.Fatal(err)
	}
	if !writeResp.Persisted || writeResp.ReceiptID == "" {
		t.Fatal("expected persisted receipt")
	}

	verify, err := svc.Verify(ctx, writeResp.ReceiptID)
	if err != nil {
		t.Fatal(err)
	}
	if !verify.Valid {
		t.Fatalf("expected valid receipt: %s", verify.Reason)
	}

	query, err := svc.Query(ctx, models.QueryRequest{TenantID: "acme", Limit: 10})
	if err != nil {
		t.Fatal(err)
	}
	if len(query.Receipts) != 1 {
		t.Fatalf("expected 1 receipt, got %d", len(query.Receipts))
	}
}

func TestWriteGetFromStoreVerifyUntouched(t *testing.T) {
	svc := newTestService(t)
	ctx := context.Background()

	writeResp, err := svc.Write(ctx, models.WriteReceiptRequest{
		EventType:    models.EventInputDefense,
		TenantID:     "acme",
		Trace:        &models.TraceContext{TraceID: "roundtrip"},
		InputVerdict: json.RawMessage(`{"action":"BLOCK","fused_score":0.88}`),
	})
	if err != nil {
		t.Fatal(err)
	}

	loaded, err := svc.Get(ctx, writeResp.ReceiptID)
	if err != nil {
		t.Fatal(err)
	}
	if loaded.ReceiptID != writeResp.ReceiptID {
		t.Fatalf("expected receipt_id %q, got %q", writeResp.ReceiptID, loaded.ReceiptID)
	}

	verify, err := svc.Verify(ctx, writeResp.ReceiptID)
	if err != nil {
		t.Fatal(err)
	}
	if !verify.Valid {
		t.Fatalf("expected untouched receipt loaded from store to verify: %s", verify.Reason)
	}
}

func TestExportJSON(t *testing.T) {
	svc := newTestService(t)
	ctx := context.Background()
	_, err := svc.Write(ctx, models.WriteReceiptRequest{
		EventType:      models.EventToolGate,
		TenantID:       "default",
		ToolDecision:   json.RawMessage(`{"status":"DENIED"}`),
	})
	if err != nil {
		t.Fatal(err)
	}

	data, contentType, filename, err := svc.Export(ctx, models.ExportRequest{
		TenantID: "default",
		Format:   "json",
	})
	if err != nil {
		t.Fatal(err)
	}
	if contentType != "application/json" || filename != "audit-export.json" {
		t.Fatalf("unexpected export metadata: %s %s", contentType, filename)
	}
	var receipts []models.Receipt
	if err := json.Unmarshal(data, &receipts); err != nil {
		t.Fatal(err)
	}
	if len(receipts) != 1 {
		t.Fatalf("expected 1 exported receipt, got %d", len(receipts))
	}
}

func TestQueryTimeFilter(t *testing.T) {
	svc := newTestService(t)
	ctx := context.Background()
	_, err := svc.Write(ctx, models.WriteReceiptRequest{
		EventType: models.EventOutputDefense,
		TenantID:  "default",
	})
	if err != nil {
		t.Fatal(err)
	}

	past := time.Now().UTC().Add(-time.Hour)
	future := time.Now().UTC().Add(time.Hour)
	resp, err := svc.Query(ctx, models.QueryRequest{
		TenantID:  "default",
		StartTime: &past,
		EndTime:   &future,
		Limit:     5,
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(resp.Receipts) != 1 {
		t.Fatalf("expected 1 receipt in window, got %d", len(resp.Receipts))
	}
}
