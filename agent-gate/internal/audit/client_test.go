package audit

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/aegis-platform/aegis/agent-gate/internal/models"
)

// EmitToolGate fires its HTTP write in a goroutine (see write()'s `go` call
// in the caller), so tests need to wait for the request to actually land
// rather than asserting immediately after the call returns.
func TestEmitToolGate_IncludesToolNameAndAgentID(t *testing.T) {
	var (
		mu   sync.Mutex
		body map[string]any
		done = make(chan struct{})
	)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Errorf("failed to decode receipt body: %v", err)
		}
		w.WriteHeader(http.StatusOK)
		close(done)
	}))
	defer srv.Close()

	c := NewClient(srv.URL, "test-token")
	if !c.Enabled() {
		t.Fatal("client should be enabled when baseURL is set")
	}

	decision := models.ToolCallDecision{Status: models.StatusApproved, DecidedAt: time.Now()}
	c.EmitToolGate("default", &TraceContext{TraceID: "trace-1"}, "delete_database", "agent-42", "fp-abc123", decision, "allow")

	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for audit receipt to be posted")
	}

	mu.Lock()
	defer mu.Unlock()

	if body["event_type"] != "TOOL_GATE" {
		t.Fatalf("expected event_type TOOL_GATE, got %v", body["event_type"])
	}
	toolDecision, ok := body["tool_decision"].(map[string]any)
	if !ok {
		t.Fatalf("tool_decision missing or wrong type: %v", body["tool_decision"])
	}
	if toolDecision["tool_name"] != "delete_database" {
		t.Errorf("expected tool_name 'delete_database' in the audit receipt, got %v -- without this, ASI10 rogue-agent pattern queries can't tell which tool was called", toolDecision["tool_name"])
	}
	if toolDecision["agent_id"] != "agent-42" {
		t.Errorf("expected agent_id 'agent-42' in the audit receipt, got %v -- without this, ASI10 rogue-agent pattern queries can't attribute a tool call to a specific agent over time", toolDecision["agent_id"])
	}
	if toolDecision["service_key_fingerprint"] != "fp-abc123" {
		t.Errorf("expected service_key_fingerprint 'fp-abc123' in the audit receipt, got %v -- without this, scripts/asi07-identity-consistency-query.py can't cross-check agent_id claims against the credential that actually authenticated the request", toolDecision["service_key_fingerprint"])
	}
}

func TestEmitToolGate_DisabledClientDoesNotPanic(t *testing.T) {
	c := NewClient("", "")
	if c.Enabled() {
		t.Fatal("client with empty baseURL should be disabled")
	}
	// Should be a no-op, not a panic or a hang.
	c.EmitToolGate("default", nil, "some_tool", "some-agent", "fp-abc123", models.ToolCallDecision{}, "allow")
}
