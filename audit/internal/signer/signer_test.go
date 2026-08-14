package signer_test

import (
	"crypto/ed25519"
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
		ReceiptID:    "11111111-1111-1111-1111-111111111111",
		EventType:    models.EventInputDefense,
		TenantID:     "default",
		Trace:        &models.TraceContext{TraceID: "trace-1", RequestID: "req-1"},
		InputVerdict: []byte(`{"action":"BLOCK","fused_score":0.91}`),
		CreatedAt:    time.Date(2026, 6, 22, 12, 0, 0, 0, time.UTC),
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

// TestVerifyFailsAfterSignerKeyRotation covers the case where the new
// signer has no record of the old key at all (nil history) -- it must
// still fail closed, not silently accept an unrelated key's signature.
// For the case where the old key IS preserved via
// AEGIS_AUDIT_SIGNING_KEYS_HISTORY, see TestVerifySucceedsAfterRotationWithHistory.
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
		ReceiptID:    "44444444-4444-4444-4444-444444444444",
		EventType:    models.EventInputDefense,
		TenantID:     "default",
		InputVerdict: []byte(`{"action":"BLOCK","fused_score":0.91}`),
		CreatedAt:    time.Date(2026, 6, 22, 12, 0, 0, 0, time.UTC),
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
	sg2, err := signer.New("seed-key", encoded, nil)
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


func TestVerifySucceedsAfterRotationWithHistory(t *testing.T) {
	sgOld, err := signer.GenerateDev("key-v1")
	if err != nil {
		t.Fatal(err)
	}
	receipt := models.Receipt{
		ReceiptID:    "55555555-5555-5555-5555-555555555555",
		EventType:    models.EventInputDefense,
		TenantID:     "default",
		InputVerdict: []byte(`{"action":"BLOCK","fused_score":0.91}`),
		CreatedAt:    time.Date(2026, 6, 22, 12, 0, 0, 0, time.UTC),
	}
	if err := sgOld.SignReceipt(&receipt); err != nil {
		t.Fatal(err)
	}

	// New signer, rotated to a fresh key -- but with key-v1's public key
	// preserved in history, the way scripts/generate-credentials.sh does
	// on rotation.
	history := map[string]ed25519.PublicKey{"key-v1": sgOld.PublicKey()}
	sgNew, err := signer.New("key-v2", base64.StdEncoding.EncodeToString(make([]byte, ed25519.SeedSize)), history)
	if err != nil {
		t.Fatal(err)
	}

	valid, reason := sgNew.VerifyReceipt(&receipt)
	if !valid {
		t.Fatalf("expected receipt signed under a retired-but-recorded key to verify, got %q", reason)
	}
}

func TestVerifyFailsForTrulyUnknownKeyID(t *testing.T) {
	sgOld, err := signer.GenerateDev("key-v1")
	if err != nil {
		t.Fatal(err)
	}
	receipt := models.Receipt{
		ReceiptID:    "66666666-6666-6666-6666-666666666666",
		EventType:    models.EventInputDefense,
		TenantID:     "default",
		InputVerdict: []byte(`{"action":"BLOCK","fused_score":0.91}`),
		CreatedAt:    time.Date(2026, 6, 22, 12, 0, 0, 0, time.UTC),
	}
	if err := sgOld.SignReceipt(&receipt); err != nil {
		t.Fatal(err)
	}

	// New signer with a history that does NOT include key-v1 at all.
	otherHistory := map[string]ed25519.PublicKey{"key-unrelated": make([]byte, ed25519.PublicKeySize)}
	sgNew, err := signer.New("key-v2", base64.StdEncoding.EncodeToString(make([]byte, ed25519.SeedSize)), otherHistory)
	if err != nil {
		t.Fatal(err)
	}

	valid, reason := sgNew.VerifyReceipt(&receipt)
	if valid {
		t.Fatal("expected verification to fail for a key id with no record anywhere")
	}
	if reason == "" || reason == "payload hash mismatch (tampered)" {
		t.Fatalf("expected an 'unknown signing key id' style reason, got %q", reason)
	}
}

func TestNewRejectsCurrentKeyIDInHistory(t *testing.T) {
	history := map[string]ed25519.PublicKey{"dup-key": make([]byte, ed25519.PublicKeySize)}
	_, err := signer.New("dup-key", base64.StdEncoding.EncodeToString(make([]byte, ed25519.SeedSize)), history)
	if err == nil {
		t.Fatal("expected an error when the current key id also appears in the historical keys map")
	}
}

func TestParseHistoricalKeys(t *testing.T) {
	pub := make([]byte, ed25519.PublicKeySize)
	for i := range pub {
		pub[i] = byte(i)
	}
	pubB64 := base64.StdEncoding.EncodeToString(pub)

	t.Run("empty input", func(t *testing.T) {
		keys, err := signer.ParseHistoricalKeys("")
		if err != nil {
			t.Fatal(err)
		}
		if keys != nil {
			t.Fatalf("expected nil map for empty input, got %v", keys)
		}
	})

	t.Run("single valid entry", func(t *testing.T) {
		keys, err := signer.ParseHistoricalKeys("key-v1:" + pubB64)
		if err != nil {
			t.Fatal(err)
		}
		if len(keys) != 1 || string(keys["key-v1"]) != string(pub) {
			t.Fatalf("unexpected parse result: %v", keys)
		}
	})

	t.Run("multiple entries", func(t *testing.T) {
		keys, err := signer.ParseHistoricalKeys("key-v1:" + pubB64 + ",key-v2:" + pubB64)
		if err != nil {
			t.Fatal(err)
		}
		if len(keys) != 2 {
			t.Fatalf("expected 2 entries, got %d", len(keys))
		}
	})

	t.Run("missing colon", func(t *testing.T) {
		if _, err := signer.ParseHistoricalKeys("key-v1-" + pubB64); err == nil {
			t.Fatal("expected an error for a malformed entry")
		}
	})

	t.Run("bad base64", func(t *testing.T) {
		if _, err := signer.ParseHistoricalKeys("key-v1:not-base64!!!"); err == nil {
			t.Fatal("expected an error for invalid base64")
		}
	})

	t.Run("wrong length key", func(t *testing.T) {
		short := base64.StdEncoding.EncodeToString([]byte("too-short"))
		if _, err := signer.ParseHistoricalKeys("key-v1:" + short); err == nil {
			t.Fatal("expected an error for a public key of the wrong length")
		}
	})

	t.Run("duplicate id, same key is fine", func(t *testing.T) {
		keys, err := signer.ParseHistoricalKeys("key-v1:" + pubB64 + ",key-v1:" + pubB64)
		if err != nil {
			t.Fatal(err)
		}
		if len(keys) != 1 {
			t.Fatalf("expected 1 entry, got %d", len(keys))
		}
	})

	t.Run("duplicate id, different key is an error", func(t *testing.T) {
		otherPub := make([]byte, ed25519.PublicKeySize)
		for i := range otherPub {
			otherPub[i] = byte(255 - i)
		}
		otherB64 := base64.StdEncoding.EncodeToString(otherPub)
		if _, err := signer.ParseHistoricalKeys("key-v1:" + pubB64 + ",key-v1:" + otherB64); err == nil {
			t.Fatal("expected an error when the same key id maps to two different public keys")
		}
	})
}
