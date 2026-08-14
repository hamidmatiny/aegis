package signer

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/aegis-platform/aegis/audit/internal/models"
)

type Signer struct {
	keyID      string
	privateKey ed25519.PrivateKey
	publicKey  ed25519.PublicKey
	// historicalKeys holds the public keys of retired signing keys, keyed
	// by their key ID, so receipts signed before a rotation can still be
	// verified. Only public keys are ever needed here -- once a key is
	// retired, its private half is discarded and never required again.
	// See ParseHistoricalKeys (AEGIS_AUDIT_SIGNING_KEYS_HISTORY).
	historicalKeys map[string]ed25519.PublicKey
}

func New(keyID, keyMaterial string, historicalKeys map[string]ed25519.PublicKey) (*Signer, error) {
	if keyID == "" {
		keyID = "dev-key-1"
	}
	if _, current := historicalKeys[keyID]; current {
		return nil, fmt.Errorf("key id %q is both the current signing key and listed in AEGIS_AUDIT_SIGNING_KEYS_HISTORY -- a retired key's id must not be reused for the active key", keyID)
	}

	priv, pub, err := parseKeyMaterial(keyMaterial)
	if err != nil {
		return nil, err
	}
	return &Signer{
		keyID:          keyID,
		privateKey:     priv,
		publicKey:      pub,
		historicalKeys: historicalKeys,
	}, nil
}

func GenerateDev(keyID string) (*Signer, error) {
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return nil, err
	}
	if keyID == "" {
		keyID = "dev-key-1"
	}
	return &Signer{keyID: keyID, privateKey: priv, publicKey: pub}, nil
}

func (s *Signer) KeyID() string {
	return s.keyID
}

func (s *Signer) PublicKey() ed25519.PublicKey {
	return s.publicKey
}

func (s *Signer) HashReceipt(receipt *models.Receipt) ([]byte, error) {
	body, err := canonicalBody(receipt)
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(body)
	return sum[:], nil
}

func (s *Signer) SignReceipt(receipt *models.Receipt) error {
	hash, err := s.HashReceipt(receipt)
	if err != nil {
		return err
	}
	receipt.PayloadHash = hash
	receipt.SignerKeyID = s.keyID
	receipt.Signature = ed25519.Sign(s.privateKey, hash)
	return nil
}

func (s *Signer) VerifyReceipt(receipt *models.Receipt) (bool, string) {
	if len(receipt.Signature) == 0 || len(receipt.PayloadHash) == 0 {
		return false, "missing signature or payload hash"
	}
	hash, err := s.HashReceipt(receipt)
	if err != nil {
		return false, err.Error()
	}
	if !bytesEqual(hash, receipt.PayloadHash) {
		return false, "payload hash mismatch (tampered)"
	}
	pubKey, ok := s.publicKeyForVerification(receipt.SignerKeyID)
	if !ok {
		return false, fmt.Sprintf(
			"unknown signing key id %q -- not the current signer's key (%q) and not present in AEGIS_AUDIT_SIGNING_KEYS_HISTORY; this receipt cannot be verified",
			receipt.SignerKeyID, s.keyID,
		)
	}
	if !ed25519.Verify(pubKey, hash, receipt.Signature) {
		return false, fmt.Sprintf("invalid Ed25519 signature for key id %q", receipt.SignerKeyID)
	}
	return true, ""
}

// publicKeyForVerification returns the public key that should verify a
// receipt signed by keyID: the current signer's own key if it matches,
// otherwise a lookup in historicalKeys for a retired key of that id.
func (s *Signer) publicKeyForVerification(keyID string) (ed25519.PublicKey, bool) {
	if keyID == s.keyID {
		return s.publicKey, true
	}
	pub, ok := s.historicalKeys[keyID]
	return pub, ok
}

// ParseHistoricalKeys parses AEGIS_AUDIT_SIGNING_KEYS_HISTORY: a
// comma-separated list of "keyID:base64PublicKey" pairs holding the
// public keys of retired signing keys. Returns (nil, nil) for an empty
// input -- no keys have been rotated yet, which is the common case.
func ParseHistoricalKeys(raw string) (map[string]ed25519.PublicKey, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil, nil
	}
	keys := make(map[string]ed25519.PublicKey)
	for _, entry := range strings.Split(raw, ",") {
		entry = strings.TrimSpace(entry)
		if entry == "" {
			continue
		}
		parts := strings.SplitN(entry, ":", 2)
		if len(parts) != 2 {
			return nil, fmt.Errorf("invalid AEGIS_AUDIT_SIGNING_KEYS_HISTORY entry %q: expected keyID:base64PublicKey", entry)
		}
		keyID, encoded := strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
		if keyID == "" {
			return nil, fmt.Errorf("invalid AEGIS_AUDIT_SIGNING_KEYS_HISTORY entry %q: empty key id", entry)
		}
		decoded, err := base64.StdEncoding.DecodeString(encoded)
		if err != nil {
			return nil, fmt.Errorf("invalid AEGIS_AUDIT_SIGNING_KEYS_HISTORY entry for key id %q: %w", keyID, err)
		}
		if len(decoded) != ed25519.PublicKeySize {
			return nil, fmt.Errorf(
				"invalid AEGIS_AUDIT_SIGNING_KEYS_HISTORY entry for key id %q: expected a %d-byte Ed25519 public key, got %d bytes",
				keyID, ed25519.PublicKeySize, len(decoded),
			)
		}
		if existing, dup := keys[keyID]; dup && !bytesEqual(existing, decoded) {
			return nil, fmt.Errorf("invalid AEGIS_AUDIT_SIGNING_KEYS_HISTORY: key id %q appears twice with different public keys", keyID)
		}
		keys[keyID] = ed25519.PublicKey(decoded)
	}
	return keys, nil
}

func canonicalBody(receipt *models.Receipt) ([]byte, error) {
	type signable struct {
		ReceiptID         string               `json:"receipt_id"`
		EventType         string               `json:"event_type"`
		TenantID          string               `json:"tenant_id"`
		Trace             *models.TraceContext `json:"trace,omitempty"`
		InputVerdict      json.RawMessage      `json:"input_verdict,omitempty"`
		PolicyDecision    json.RawMessage      `json:"policy_decision,omitempty"`
		OutputVerdict     json.RawMessage      `json:"output_verdict,omitempty"`
		ToolDecision      json.RawMessage      `json:"tool_decision,omitempty"`
		PolicyPackID      string               `json:"policy_pack_id,omitempty"`
		PolicyPackVersion string               `json:"policy_pack_version,omitempty"`
		Metadata          json.RawMessage      `json:"metadata,omitempty"`
		CreatedAt         string               `json:"created_at"`
	}
	body := signable{
		ReceiptID:         receipt.ReceiptID,
		EventType:         receipt.EventType,
		TenantID:          receipt.TenantID,
		Trace:             receipt.Trace,
		InputVerdict:      normalizeRawJSON(receipt.InputVerdict),
		PolicyDecision:    normalizeRawJSON(receipt.PolicyDecision),
		OutputVerdict:     normalizeRawJSON(receipt.OutputVerdict),
		ToolDecision:      normalizeRawJSON(receipt.ToolDecision),
		PolicyPackID:      receipt.PolicyPackID,
		PolicyPackVersion: receipt.PolicyPackVersion,
		Metadata:          normalizeRawJSON(receipt.Metadata),
		CreatedAt:         receipt.CreatedAt.UTC().Truncate(time.Microsecond).Format(timeRFC3339Micro),
	}
	return json.Marshal(body)
}

const timeRFC3339Micro = "2006-01-02T15:04:05.999999Z07:00"

func normalizeRawJSON(raw json.RawMessage) json.RawMessage {
	if len(raw) == 0 {
		return nil
	}
	var value any
	if err := json.Unmarshal(raw, &value); err != nil {
		return raw
	}
	out, err := json.Marshal(value)
	if err != nil {
		return raw
	}
	return out
}

func parseKeyMaterial(material string) (ed25519.PrivateKey, ed25519.PublicKey, error) {
	material = strings.TrimSpace(material)
	if material == "" {
		return nil, nil, errors.New("empty signing key")
	}

	if strings.HasPrefix(material, "-----BEGIN") {
		block, _ := pem.Decode([]byte(material))
		if block == nil {
			return nil, nil, errors.New("invalid PEM signing key")
		}
		if block.Type != "PRIVATE KEY" {
			return nil, nil, fmt.Errorf("unsupported PEM type %q", block.Type)
		}
		priv, err := parsePKCS8Ed25519(block.Bytes)
		if err != nil {
			return nil, nil, err
		}
		return priv, priv.Public().(ed25519.PublicKey), nil
	}

	raw, err := base64.StdEncoding.DecodeString(material)
	if err != nil {
		return nil, nil, fmt.Errorf("signing key must be PEM or base64 seed: %w", err)
	}
	switch len(raw) {
	case ed25519.SeedSize:
		priv := ed25519.NewKeyFromSeed(raw)
		return priv, priv.Public().(ed25519.PublicKey), nil
	case ed25519.PrivateKeySize:
		priv := ed25519.PrivateKey(raw)
		return priv, priv.Public().(ed25519.PublicKey), nil
	default:
		return nil, nil, fmt.Errorf("unexpected key length %d", len(raw))
	}
}

func bytesEqual(a, b []byte) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
