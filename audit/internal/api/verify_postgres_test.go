package api_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"github.com/aegis-platform/aegis/audit/internal/api"
	"github.com/aegis-platform/aegis/audit/internal/models"
	"github.com/aegis-platform/aegis/audit/internal/service"
	"github.com/aegis-platform/aegis/audit/internal/signer"
	"github.com/aegis-platform/aegis/audit/internal/store"
)

const testDevSigningSeed = "YWVnaXMtZGV2LWF1ZGl0LXNpZ25pbmcta2V5LXYxISE="

func newPostgresTestServer(t *testing.T) *httptest.Server {
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

	sg, err := signer.New("api-postgres-test", testDevSigningSeed)
	if err != nil {
		t.Fatal(err)
	}
	svc := service.New(st, sg)
	mux := http.NewServeMux()
	api.NewServer(svc).Register(mux)
	return httptest.NewServer(mux)
}

func TestHTTPVerifyAfterPostgresRoundTrip(t *testing.T) {
	srv := newPostgresTestServer(t)
	defer srv.Close()

	payload := models.WriteReceiptRequest{
		EventType:    models.EventInputDefense,
		TenantID:     "default",
		Trace:        &models.TraceContext{TraceID: "http-pg-roundtrip", RequestID: "req-1"},
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
	if writeResp.ReceiptID == "" {
		t.Fatal("expected receipt_id")
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
		t.Fatalf("expected valid receipt after postgres round-trip: %s", verify.Reason)
	}
}
