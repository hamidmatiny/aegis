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
}

func New(keyID, keyMaterial string) (*Signer, error) {
	if keyID == "" {
		keyID = "dev-key-1"
	}

	priv, pub, err := parseKeyMaterial(keyMaterial)
	if err != nil {
		return nil, err
	}
	return &Signer{
		keyID:      keyID,
		privateKey: priv,
		publicKey:  pub,
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
	if !ed25519.Verify(s.publicKey, hash, receipt.Signature) {
		return false, "invalid Ed25519 signature (payload hash matches; signing key may have rotated since receipt was created)"
	}
	return true, ""
}

func canonicalBody(receipt *models.Receipt) ([]byte, error) {
	type signable struct {
		ReceiptID         string                `json:"receipt_id"`
		EventType         string                `json:"event_type"`
		TenantID          string                `json:"tenant_id"`
		Trace             *models.TraceContext  `json:"trace,omitempty"`
		InputVerdict      json.RawMessage       `json:"input_verdict,omitempty"`
		PolicyDecision    json.RawMessage       `json:"policy_decision,omitempty"`
		OutputVerdict     json.RawMessage       `json:"output_verdict,omitempty"`
		ToolDecision      json.RawMessage       `json:"tool_decision,omitempty"`
		PolicyPackID      string                `json:"policy_pack_id,omitempty"`
		PolicyPackVersion string                `json:"policy_pack_version,omitempty"`
		Metadata          json.RawMessage       `json:"metadata,omitempty"`
		CreatedAt         string                `json:"created_at"`
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
