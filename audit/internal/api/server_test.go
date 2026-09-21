package api_test

import (
	"bytes"
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aegis-platform/aegis/audit/internal/api"
	"github.com/aegis-platform/aegis/audit/internal/models"
	"github.com/aegis-platform/aegis/audit/internal/service"
	"github.com/aegis-platform/aegis/audit/internal/signer"
	"github.com/aegis-platform/aegis/audit/internal/store"
)

func newTestServer(t *testing.T) *httptest.Server {
	t.Helper()
	sg, err := signer.GenerateDev("api-test")
	if err != nil {
		t.Fatal(err)
	}
	svc := service.New(store.NewMemoryStore(), sg)
	mux := http.NewServeMux()
	api.NewServer(svc).Register(mux)
	return httptest.NewServer(mux)
}

func TestHealth(t *testing.T) {
	srv := newTestServer(t)
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/health")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status %d", resp.StatusCode)
	}
	var body map[string]string
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if body["stage"] != "8" {
		t.Fatalf("expected stage 8, got %q", body["stage"])
	}
}

func TestWriteAndVerifyFlow(t *testing.T) {
	srv := newTestServer(t)
	defer srv.Close()

	payload := models.WriteReceiptRequest{
		EventType:    models.EventInputDefense,
		TenantID:     "default",
		InputVerdict: json.RawMessage(`{"action":"BLOCK","fused_score":0.95}`),
	}
	body, _ := json.Marshal(payload)
	resp, err := http.Post(srv.URL+"/v1/receipts", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("write status %d", resp.StatusCode)
	}
	var writeResp models.WriteReceiptResponse
	if err := json.NewDecoder(resp.Body).Decode(&writeResp); err != nil {
		t.Fatal(err)
	}

	verifyResp, err := http.Get(srv.URL + "/v1/receipts/" + writeResp.ReceiptID + "/verify")
	if err != nil {
		t.Fatal(err)
	}
	defer verifyResp.Body.Close()
	var verify models.VerifyResponse
	if err := json.NewDecoder(verifyResp.Body).Decode(&verify); err != nil {
		t.Fatal(err)
	}
	if !verify.Valid {
		t.Fatalf("expected valid receipt: %s", verify.Reason)
	}
}

func TestKeysPublication(t *testing.T) {
	pub, _, err := ed25519.GenerateKey(nil)
	if err != nil {
		t.Fatal(err)
	}
	history := map[string]ed25519.PublicKey{"retired-key": pub}
	// Build signer with known history via New + seed.
	seed := make([]byte, ed25519.SeedSize)
	for i := range seed {
		seed[i] = byte(i + 1)
	}
	sg, err := signer.New("active-key", base64.StdEncoding.EncodeToString(seed), history)
	if err != nil {
		t.Fatal(err)
	}
	svc := service.New(store.NewMemoryStore(), sg)
	mux := http.NewServeMux()
	api.NewServer(svc).WithKeysURI("https://audit.example/.well-known/jwks.json").Register(mux)
	srv := httptest.NewServer(mux)
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/v1/keys")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("JWKS status %d", resp.StatusCode)
	}
	var jwks models.JWKS
	if err := json.NewDecoder(resp.Body).Decode(&jwks); err != nil {
		t.Fatal(err)
	}
	if len(jwks.Keys) != 2 {
		t.Fatalf("expected 2 keys, got %d", len(jwks.Keys))
	}
	byKid := map[string]models.JWK{}
	for _, k := range jwks.Keys {
		byKid[k.Kid] = k
	}
	if byKid["active-key"].AegisStatus != models.KeyStatusActive {
		t.Fatalf("active status=%q", byKid["active-key"].AegisStatus)
	}
	if byKid["retired-key"].AegisStatus != models.KeyStatusRetired {
		t.Fatalf("retired status=%q", byKid["retired-key"].AegisStatus)
	}
	if byKid["retired-key"].AegisCompromisedAt != nil {
		t.Fatal("retired must not imply compromised")
	}

	one, err := http.Get(srv.URL + "/v1/keys/active-key")
	if err != nil {
		t.Fatal(err)
	}
	defer one.Body.Close()
	if one.StatusCode != http.StatusOK {
		t.Fatalf("key by id status %d", one.StatusCode)
	}

	missing, err := http.Get(srv.URL + "/v1/keys/does-not-exist")
	if err != nil {
		t.Fatal(err)
	}
	defer missing.Body.Close()
	if missing.StatusCode != http.StatusNotFound {
		t.Fatalf("unknown key status %d", missing.StatusCode)
	}

	alias, err := http.Get(srv.URL + "/.well-known/jwks.json")
	if err != nil {
		t.Fatal(err)
	}
	defer alias.Body.Close()
	if alias.StatusCode != http.StatusOK {
		t.Fatalf("well-known status %d", alias.StatusCode)
	}

	// Export advertises keys_uri as metadata header only.
	expBody, _ := json.Marshal(models.ExportRequest{TenantID: "default", Format: "json"})
	exp, err := http.Post(srv.URL+"/v1/export", "application/json", bytes.NewReader(expBody))
	if err != nil {
		t.Fatal(err)
	}
	defer exp.Body.Close()
	if got := exp.Header.Get("X-Aegis-Keys-Uri"); got != "https://audit.example/.well-known/jwks.json" {
		t.Fatalf("keys uri header %q", got)
	}
}
