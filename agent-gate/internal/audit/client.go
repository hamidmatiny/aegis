package audit

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"time"

	"github.com/aegis-platform/aegis/agent-gate/internal/models"
)

// TraceContext correlates receipts across the defense pipeline.
type TraceContext struct {
	TraceID   string `json:"trace_id,omitempty"`
	RequestID string `json:"request_id,omitempty"`
}

// Client emits signed receipts to the audit service.
type Client struct {
	baseURL string
	client  *http.Client
	enabled bool
}

func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: baseURL,
		enabled: baseURL != "",
		client:  &http.Client{Timeout: 5 * time.Second},
	}
}

func (c *Client) Enabled() bool {
	return c.enabled
}

func (c *Client) EmitToolGate(
	tenantID string,
	trace *TraceContext,
	toolName string,
	agentID string,
	decision models.ToolCallDecision,
	policyAction string,
) {
	if !c.enabled {
		return
	}
	// tool_name and agent_id are required for any pattern-over-time analysis
	// of a single agent's tool-call history (ASI10, OWASP Agentic Top 10) --
	// without them the audit trail records *that* a call happened but not
	// *what* was called or *by whom*, which makes "an agent that suddenly
	// starts calling delete_* tools it never called before" unqueryable.
	toolPayload := map[string]any{
		"tool_name":             toolName,
		"agent_id":              agentID,
		"status":                decision.Status,
		"denial_reason":         decision.DenialReason,
		"violated_policies":     decision.ViolatedPolicies,
		"flagged_taint":         decision.FlaggedTaint,
		"approval_request_id":   decision.ApprovalRequestID,
		"decided_at":            decision.DecidedAt,
		"evaluation_latency_ms": decision.EvaluationLatencyMS,
		"policy_action":         policyAction,
	}
	toolJSON, err := json.Marshal(toolPayload)
	if err != nil {
		slog.Warn("audit marshal tool decision failed", "error", err)
		return
	}
	payload := map[string]any{
		"event_type":    "TOOL_GATE",
		"tenant_id":     tenantID,
		"tool_decision": json.RawMessage(toolJSON),
	}
	if trace != nil && (trace.TraceID != "" || trace.RequestID != "") {
		payload["trace"] = trace
	}
	go c.write(payload)
}

func (c *Client) write(payload map[string]any) {
	body, err := json.Marshal(payload)
	if err != nil {
		slog.Warn("audit marshal receipt failed", "error", err)
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/v1/receipts", bytes.NewReader(body))
	if err != nil {
		slog.Warn("audit request build failed", "error", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.client.Do(req)
	if err != nil {
		slog.Warn("audit emit failed", "error", err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		slog.Warn("audit emit rejected", "status", resp.StatusCode)
	}
}

func TraceFromRequest(req models.EvaluateRequest) *TraceContext {
	if req.Trace != nil && (req.Trace.TraceID != "" || req.Trace.RequestID != "") {
		return &TraceContext{
			TraceID:   req.Trace.TraceID,
			RequestID: req.Trace.RequestID,
		}
	}
	if req.ToolCall.Trace == nil {
		return nil
	}
	trace := &TraceContext{}
	if v, ok := req.ToolCall.Trace["trace_id"]; ok {
		trace.TraceID = v
	}
	if v, ok := req.ToolCall.Trace["request_id"]; ok {
		trace.RequestID = v
	}
	if trace.TraceID == "" && trace.RequestID == "" {
		return nil
	}
	return trace
}
