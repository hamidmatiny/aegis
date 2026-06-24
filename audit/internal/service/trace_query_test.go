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

func TestQueryByTraceID(t *testing.T) {
	sg, err := signer.GenerateDev("test")
	if err != nil {
		t.Fatal(err)
	}
	svc := service.New(store.NewMemoryStore(), sg)
	ctx := context.Background()

	trace := &models.TraceContext{TraceID: "trace-xyz", RequestID: "req-1"}
	_, err = svc.Write(ctx, models.WriteReceiptRequest{
		EventType: models.EventInputDefense,
		TenantID:  "default",
		Trace:     trace,
		InputVerdict: json.RawMessage(`{"action":"BLOCK","fused_score":0.9}`),
	})
	if err != nil {
		t.Fatal(err)
	}
	time.Sleep(10 * time.Millisecond)

	resp, err := svc.Query(ctx, models.QueryRequest{TraceID: "trace-xyz", Limit: 10})
	if err != nil {
		t.Fatal(err)
	}
	if len(resp.Receipts) != 1 {
		t.Fatalf("expected 1 receipt, got %d", len(resp.Receipts))
	}
	if resp.Receipts[0].Trace == nil || resp.Receipts[0].Trace.TraceID != "trace-xyz" {
		t.Fatalf("unexpected trace: %+v", resp.Receipts[0].Trace)
	}
}
