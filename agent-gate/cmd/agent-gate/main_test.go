package main_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aegis-platform/aegis/agent-gate/internal/api"
	"github.com/aegis-platform/aegis/agent-gate/internal/approval"
	"github.com/aegis-platform/aegis/agent-gate/internal/audit"
	"github.com/aegis-platform/aegis/agent-gate/internal/gate"
	"github.com/aegis-platform/aegis/agent-gate/internal/policy"
)

func TestHealthEndpoint(t *testing.T) {
	policySrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer policySrv.Close()

	mux := http.NewServeMux()
	g := gate.New(policy.NewClient(policySrv.URL), approval.NewStore(0))
	api.NewServer(g, audit.NewClient("")).Register(mux)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["service"] != "agent-gate" || body["stage"] != "6" {
		t.Fatalf("unexpected body: %v", body)
	}
}

func TestListApprovalsEndpoint(t *testing.T) {
	policySrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"decision": map[string]string{"action": "escalate_to_judge"},
		})
	}))
	defer policySrv.Close()

	mux := http.NewServeMux()
	g := gate.New(policy.NewClient(policySrv.URL), approval.NewStore(0))
	api.NewServer(g, audit.NewClient("")).Register(mux)

	evalBody := []byte(`{
		"tenant_id":"default",
		"tool_call":{"tool_name":"delete_db","risk_level":"IRREVERSIBLE","arguments":[{"name":"target"}]}
	}`)
	req := httptest.NewRequest(http.MethodPost, "/v1/evaluate", bytes.NewReader(evalBody))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("evaluate status %d body %s", rec.Code, rec.Body.String())
	}

	req = httptest.NewRequest(http.MethodGet, "/v1/approvals", nil)
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("list approvals status %d", rec.Code)
	}
	var list map[string][]map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &list); err != nil {
		t.Fatal(err)
	}
	if len(list["approvals"]) != 1 {
		t.Fatalf("expected 1 pending approval, got %d", len(list["approvals"]))
	}
}
