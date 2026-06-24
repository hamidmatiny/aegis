package api_test

import (
	"bytes"
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
		EventType: models.EventInputDefense,
		TenantID:  "default",
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
