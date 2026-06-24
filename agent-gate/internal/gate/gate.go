package gate

import (
	"context"
	"fmt"
	"time"

	"github.com/aegis-platform/aegis/agent-gate/internal/approval"
	"github.com/aegis-platform/aegis/agent-gate/internal/mask"
	"github.com/aegis-platform/aegis/agent-gate/internal/models"
	"github.com/aegis-platform/aegis/agent-gate/internal/policy"
	"github.com/aegis-platform/aegis/agent-gate/internal/taint"
)

// Gate enforces deterministic tool permissions via policy-engine and code-level checks.
type Gate struct {
	policy    *policy.Client
	approvals *approval.Store
}

func New(policyClient *policy.Client, approvalStore *approval.Store) *Gate {
	return &Gate{policy: policyClient, approvals: approvalStore}
}

// Evaluate sanitizes arguments, calls policy-engine, and maps to ToolCallStatus.
func (g *Gate) Evaluate(ctx context.Context, req models.EvaluateRequest) (*models.EvaluateResponse, error) {
	start := time.Now()

	call := req.ToolCall
	call.RiskLevel = taint.DefaultRiskLevel(call.RiskLevel)
	sanitized := mask.SanitizeToolCall(call)
	sanitized.RiskLevel = call.RiskLevel
	sanitized.TaintLabels = taint.CollectLabels(sanitized)

	mode := req.Mode
	if mode == "" {
		mode = models.ModeEnforce
	}

	policyDecision, err := g.policy.EvaluateTool(ctx, models.PolicyEvaluateToolRequest{
		ToolCall:     policy.ToPolicyToolCall(sanitized),
		TenantID:     req.TenantID,
		PolicyPackID: req.PolicyPackID,
		Mode:         mode,
	})
	if err != nil {
		return nil, err
	}

	decision := models.ToolCallDecision{
		FlaggedTaint:        taint.FlaggedTaint(sanitized.Arguments),
		DecidedAt:           time.Now().UTC(),
		EvaluationLatencyMS: time.Since(start).Milliseconds(),
	}

	switch policyDecision.Action {
	case "block":
		decision.Status = models.StatusDenied
		decision.DenialReason = policyDecision.BlockReason
		if decision.DenialReason == "" {
			decision.DenialReason = "blocked by policy"
		}
		decision.ViolatedPolicies = []string{policyDecision.BlockReason}

	case "escalate_to_judge":
		appr, err := g.approvals.Create(sanitized, req.TenantID)
		if err != nil {
			return nil, err
		}
		decision.Status = models.StatusAwaitingHumanApproval
		decision.ApprovalRequestID = appr.ApprovalID
		decision.DenialReason = "human approval required for irreversible or high-risk action"

	case "allow":
		decision.Status = models.StatusApproved

	default:
		decision.Status = models.StatusApproved
	}

	return &models.EvaluateResponse{
		Decision:          decision,
		SanitizedToolCall: sanitized,
		PolicyAction:      policyDecision.Action,
	}, nil
}

// SubmitApproval records a human reviewer decision on a pending approval.
func (g *Gate) SubmitApproval(_ context.Context, action models.ApprovalAction) (*models.ToolCallDecision, error) {
	if action.ApprovalID == "" {
		return nil, fmt.Errorf("approval_id required")
	}

	appr, err := g.approvals.Decide(action.ApprovalID, action)
	if err != nil {
		return nil, err
	}

	decision := models.ToolCallDecision{
		DecidedAt: time.Now().UTC(),
	}
	if appr.Status == models.StatusApproved {
		decision.Status = models.StatusApproved
	} else {
		decision.Status = models.StatusDenied
		decision.DenialReason = "denied by human reviewer"
		if action.Comment != "" {
			decision.DenialReason = action.Comment
		}
	}
	return &decision, nil
}

// GetApproval returns a pending or decided approval request.
func (g *Gate) GetApproval(_ context.Context, approvalID string) (*models.ApprovalRequest, error) {
	return g.approvals.Get(approvalID)
}

// ListApprovals returns in-memory approval requests for the dashboard inbox.
func (g *Gate) ListApprovals(pendingOnly bool) []*models.ApprovalRequest {
	return g.approvals.List(pendingOnly)
}
