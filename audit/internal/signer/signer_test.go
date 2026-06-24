package signer_test

import (
	"encoding/base64"
	"testing"
	"time"

	"github.com/aegis-platform/aegis/audit/internal/models"
	"github.com/aegis-platform/aegis/audit/internal/signer"
)

func TestSignAndVerifyReceipt(t *testing.T) {
	sg, err := signer.GenerateDev("test-key")
	if err != nil {
		t.Fatal(err)
	}

	receipt := models.Receipt{
		ReceiptID: "11111111-1111-1111-1111-111111111111",
		EventType: models.EventInputDefense,
		TenantID:  "default",
		Trace:     &models.TraceContext{TraceID: "trace-1", RequestID: "req-1"},
		InputVerdict: []byte(`{"action":"BLOCK","fused_score":0.91}`),
		CreatedAt: time.Date(2026, 6, 22, 12, 0, 0, 0, time.UTC),
	}
	if err := sg.SignReceipt(&receipt); err != nil {
		t.Fatal(err)
	}
	valid, reason := sg.VerifyReceipt(&receipt)
	if !valid {
		t.Fatalf("expected valid receipt, got %q", reason)
	}

	receipt.InputVerdict = []byte(`{"action":"ALLOW","fused_score":0.1}`)
	valid, reason = sg.VerifyReceipt(&receipt)
	if valid {
		t.Fatal("expected tampered receipt to fail verification")
	}
	if reason == "" {
		t.Fatal("expected failure reason")
	}
	if reason != "payload hash mismatch (tampered)" {
		t.Fatalf("expected tamper reason, got %q", reason)
	}
}

func TestVerifyFailsAfterSignerKeyRotation(t *testing.T) {
	sg1, err := signer.GenerateDev("key-before-restart")
	if err != nil {
		t.Fatal(err)
	}
	sg2, err := signer.GenerateDev("key-after-restart")
	if err != nil {
		t.Fatal(err)
	}

	receipt := models.Receipt{
		ReceiptID: "44444444-4444-4444-4444-444444444444",
		EventType: models.EventInputDefense,
		TenantID:  "default",
		InputVerdict: []byte(`{"action":"BLOCK","fused_score":0.91}`),
		CreatedAt: time.Date(2026, 6, 22, 12, 0, 0, 0, time.UTC),
	}
	if err := sg1.SignReceipt(&receipt); err != nil {
		t.Fatal(err)
	}

	valid, reason := sg2.VerifyReceipt(&receipt)
	if valid {
		t.Fatal("expected receipt signed with old key to fail after key rotation")
	}
	if reason == "" {
		t.Fatal("expected failure reason")
	}
	if reason == "payload hash mismatch (tampered)" {
		t.Fatal("key rotation should not look like payload tampering")
	}
}

func TestParseBase64Seed(t *testing.T) {
	dev, err := signer.GenerateDev("seed-test")
	if err != nil {
		t.Fatal(err)
	}
	receipt := models.Receipt{
		ReceiptID: "22222222-2222-2222-2222-222222222222",
		EventType: models.EventPolicyDecision,
		TenantID:  "default",
		CreatedAt: time.Now().UTC(),
	}
	if err := dev.SignReceipt(&receipt); err != nil {
		t.Fatal(err)
	}
	valid, _ := dev.VerifyReceipt(&receipt)
	if !valid {
		t.Fatal("dev signer verify failed")
	}

	seedBytes := []byte("01234567890123456789012345678901")
	encoded := base64.StdEncoding.EncodeToString(seedBytes)
	sg2, err := signer.New("seed-key", encoded)
	if err != nil {
		t.Fatal(err)
	}
	receipt2 := receipt
	receipt2.ReceiptID = "33333333-3333-3333-3333-333333333333"
	if err := sg2.SignReceipt(&receipt2); err != nil {
		t.Fatal(err)
	}
	if ok, _ := sg2.VerifyReceipt(&receipt2); !ok {
		t.Fatal("seed-based signer failed")
	}
}
