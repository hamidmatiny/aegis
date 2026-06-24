package models

import "time"

// Tool call status values (matches shared proto ToolCallStatus strings).
type ToolCallStatus string

const (
	StatusPending                ToolCallStatus = "PENDING"
	StatusApproved               ToolCallStatus = "APPROVED"
	StatusDenied                 ToolCallStatus = "DENIED"
	StatusAwaitingHumanApproval  ToolCallStatus = "AWAITING_HUMAN_APPROVAL"
	StatusExecuted               ToolCallStatus = "EXECUTED"
)

// Taint levels for tool arguments.
const (
	TaintTrusted   = "TRUSTED"
	TaintUntrusted = "UNTRUSTED"
	TaintTainted   = "TAINTED"
)

// EvaluationMode mirrors policy-engine modes.
type EvaluationMode string

const (
	ModeEnforce EvaluationMode = "enforce"
	ModeShadow  EvaluationMode = "shadow"
	ModeDryRun  EvaluationMode = "dry_run"
)

// ToolArgument is a single tool/MCP argument with taint metadata.
type ToolArgument struct {
	Name                string `json:"name"`
	Value               any    `json:"value"`
	TaintLevel          string `json:"taint_level,omitempty"`
	TaintSource         string `json:"taint_source,omitempty"`
	ContainsCredentials bool   `json:"contains_credentials,omitempty"`
	MaskedValue         string `json:"masked_value,omitempty"`
}

// TaintLabel summarizes taint on the tool call.
type TaintLabel struct {
	Source string `json:"source"`
	Level  string `json:"level"`
	Field  string `json:"field,omitempty"`
}

// ToolCallRequest is an intercepted agent tool/MCP call.
type ToolCallRequest struct {
	Trace       map[string]string `json:"trace,omitempty"`
	ToolName    string              `json:"tool_name"`
	ToolID      string              `json:"tool_id,omitempty"`
	Arguments   []ToolArgument      `json:"arguments"`
	RiskLevel   string              `json:"risk_level,omitempty"`
	TaintLabels []TaintLabel        `json:"taint_labels,omitempty"`
	AgentID     string              `json:"agent_id,omitempty"`
	RequestedAt *time.Time          `json:"requested_at,omitempty"`
}

// ToolCallDecision is the gate outcome for a tool call.
type ToolCallDecision struct {
	Status              ToolCallStatus `json:"status"`
	DenialReason        string         `json:"denial_reason,omitempty"`
	ViolatedPolicies    []string       `json:"violated_policies,omitempty"`
	FlaggedTaint        []TaintLabel   `json:"flagged_taint,omitempty"`
	ApprovalRequestID   string         `json:"approval_request_id,omitempty"`
	DecidedAt           time.Time      `json:"decided_at"`
	EvaluationLatencyMS int64          `json:"evaluation_latency_ms"`
}

// EvaluateRequest is the HTTP body for POST /v1/evaluate.
type EvaluateRequest struct {
	ToolCall     ToolCallRequest `json:"tool_call"`
	TenantID     string          `json:"tenant_id"`
	PolicyPackID string          `json:"policy_pack_id,omitempty"`
	Mode         EvaluationMode  `json:"mode,omitempty"`
}

// EvaluateResponse includes the decision and sanitized tool call for execution.
type EvaluateResponse struct {
	Decision          ToolCallDecision `json:"decision"`
	SanitizedToolCall ToolCallRequest  `json:"sanitized_tool_call"`
	PolicyAction      string           `json:"policy_action,omitempty"`
}

// ApprovalAction is a human reviewer decision.
type ApprovalAction struct {
	ApprovalID string `json:"approval_id"`
	Approved   bool   `json:"approved"`
	ReviewerID string `json:"reviewer_id"`
	Comment    string `json:"comment,omitempty"`
}

// ApprovalRequest tracks a pending human approval.
type ApprovalRequest struct {
	ApprovalID  string          `json:"approval_id"`
	ToolCall    ToolCallRequest `json:"tool_call"`
	TenantID    string          `json:"tenant_id"`
	CreatedAt   time.Time       `json:"created_at"`
	ExpiresAt   time.Time       `json:"expires_at"`
	Status      ToolCallStatus  `json:"status"`
	ReviewerID  string          `json:"reviewer_id,omitempty"`
	ReviewComment string        `json:"review_comment,omitempty"`
}

// PolicyEvaluateToolRequest is sent to policy-engine.
type PolicyEvaluateToolRequest struct {
	ToolCall     PolicyToolCallRequest `json:"tool_call"`
	TenantID     string                `json:"tenant_id"`
	PolicyPackID string                `json:"policy_pack_id,omitempty"`
	Mode         EvaluationMode        `json:"mode,omitempty"`
}

// PolicyToolCallRequest is the subset policy-engine CEL evaluates today.
type PolicyToolCallRequest struct {
	ToolName  string               `json:"tool_name"`
	RiskLevel string               `json:"risk_level,omitempty"`
	Arguments []PolicyToolArgument `json:"arguments,omitempty"`
}

// PolicyToolArgument is passed to policy-engine CEL activation.
type PolicyToolArgument struct {
	Name                string `json:"name"`
	TaintLevel          string `json:"taint_level,omitempty"`
	ContainsCredentials bool   `json:"contains_credentials"`
}

// PolicyDecision mirrors policy-engine response (subset used by gate).
type PolicyDecision struct {
	Action      string `json:"action"`
	BlockReason string `json:"block_reason,omitempty"`
}

// PolicyEvaluateResponse wraps policy-engine HTTP response.
type PolicyEvaluateResponse struct {
	Decision PolicyDecision `json:"decision"`
}
