package models

// JWK is an RFC 7517 OKP / Ed25519 public key plus AEGIS rotation metadata.
// aegis_status is "active" (may sign new receipts) or "retired" (historical
// verify only). Compromise is a separate optional field — never infer
// invalid history from "retired" alone.
type JWK struct {
	Kty                string  `json:"kty"`
	Crv                string  `json:"crv"`
	Kid                string  `json:"kid"`
	X                  string  `json:"x"`
	Use                string  `json:"use"`
	Alg                string  `json:"alg"`
	AegisStatus        string  `json:"aegis_status"`
	AegisNotBefore     *string `json:"aegis_not_before,omitempty"`
	AegisRetiredAt     *string `json:"aegis_retired_at,omitempty"`
	AegisCompromisedAt *string `json:"aegis_compromised_at,omitempty"`
}

// JWKS is an RFC 7517 JSON Web Key Set.
type JWKS struct {
	Keys []JWK `json:"keys"`
}

// Key status values for aegis_status.
const (
	KeyStatusActive  = "active"
	KeyStatusRetired = "retired"
)
