package gate_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aegis-platform/aegis/agent-gate/internal/approval"
	"github.com/aegis-platform/aegis/agent-gate/internal/gate"
	"github.com/aegis-platform/aegis/agent-gate/internal/models"
	"github.com/aegis-platform/aegis/agent-gate/internal/policy"
)

func mockPolicyServer(action, blockReason string) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/evaluate/tool" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"decision": map[string]any{
				"action":       action,
				"block_reason": blockReason,
			},
		})
	}))
}

func newTestGate(t *testing.T, action, blockReason string) *gate.Gate {
	t.Helper()
	srv := mockPolicyServer(action, blockReason)
	t.Cleanup(srv.Close)
	return gate.New(policy.NewClient(srv.URL), approval.NewStore(0))
}

func TestEvaluateAllowsBenignTool(t *testing.T) {
	g := newTestGate(t, "allow", "")
	resp, err := g.Evaluate(context.Background(), models.EvaluateRequest{
		TenantID: "default",
		ToolCall: models.ToolCallRequest{
			ToolName:  "search",
			RiskLevel: "LOW",
			Arguments: []models.ToolArgument{
				{Name: "query", Value: "weather"},
			},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Decision.Status != models.StatusApproved {
		t.Fatalf("expected APPROVED, got %s", resp.Decision.Status)
	}
}

func TestEvaluateBlocksTaintedCredentials(t *testing.T) {
	g := newTestGate(t, "block", `rule "block-tainted-credentials" matched`)
	resp, err := g.Evaluate(context.Background(), models.EvaluateRequest{
		TenantID: "default",
		ToolCall: models.ToolCallRequest{
			ToolName:  "send_email",
			RiskLevel: "MEDIUM",
			Arguments: []models.ToolArgument{
				{
					Name:                "body",
					Value:               "password: secret123",
					TaintLevel:          models.TaintTainted,
					ContainsCredentials: true,
				},
			},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Decision.Status != models.StatusDenied {
		t.Fatalf("expected DENIED, got %s", resp.Decision.Status)
	}
}

func TestEvaluateIrreversibleRequiresApproval(t *testing.T) {
	g := newTestGate(t, "escalate_to_judge", "")
	resp, err := g.Evaluate(context.Background(), models.EvaluateRequest{
		TenantID: "default",
		ToolCall: models.ToolCallRequest{
			ToolName:  "delete_database",
			RiskLevel: "IRREVERSIBLE",
			Arguments: []models.ToolArgument{
				{Name: "db_id", Value: "prod-1"},
			},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Decision.Status != models.StatusAwaitingHumanApproval {
		t.Fatalf("expected AWAITING_HUMAN_APPROVAL, got %s", resp.Decision.Status)
	}
	if resp.Decision.ApprovalRequestID == "" {
		t.Fatal("expected approval_request_id")
	}
}

func TestSubmitApprovalApproves(t *testing.T) {
	g := newTestGate(t, "escalate_to_judge", "")
	eval, err := g.Evaluate(context.Background(), models.EvaluateRequest{
		TenantID: "default",
		ToolCall: models.ToolCallRequest{
			ToolName:  "delete_file",
			RiskLevel: "IRREVERSIBLE",
		},
	})
	if err != nil {
		t.Fatal(err)
	}

	decision, err := g.SubmitApproval(context.Background(), models.ApprovalAction{
		ApprovalID: eval.Decision.ApprovalRequestID,
		Approved:   true,
		ReviewerID: "reviewer-1",
	})
	if err != nil {
		t.Fatal(err)
	}
	if decision.Status != models.StatusApproved {
		t.Fatalf("expected APPROVED after human approval, got %s", decision.Status)
	}
}

func TestSanitizedToolCallMasksCredentials(t *testing.T) {
	g := newTestGate(t, "allow", "")
	resp, err := g.Evaluate(context.Background(), models.EvaluateRequest{
		TenantID: "default",
		ToolCall: models.ToolCallRequest{
			ToolName: "run_command",
			Arguments: []models.ToolArgument{
				{Name: "cmd", Value: "curl -H 'Authorization: Bearer sk-live-abc123xyz789012345678'"},
			},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if !resp.SanitizedToolCall.Arguments[0].ContainsCredentials {
		t.Fatal("expected credential detection")
	}
	if resp.SanitizedToolCall.Arguments[0].Value == "curl -H 'Authorization: Bearer sk-live-abc123xyz789012345678'" {
		t.Fatal("expected masked value in sanitized tool call")
	}
}
