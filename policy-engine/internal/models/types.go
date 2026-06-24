package models

import (
	"encoding/json"
	"time"
)

// EvaluationMode controls whether policy decisions are enforced.
type EvaluationMode string

const (
	ModeEnforce EvaluationMode = "enforce"
	ModeShadow  EvaluationMode = "shadow"
	ModeDryRun  EvaluationMode = "dry_run"
)

// Action is a policy decision outcome.
type Action string

const (
	ActionAllow          Action = "allow"
	ActionBlock          Action = "block"
	ActionTransform      Action = "transform"
	ActionEscalateToJudge Action = "escalate_to_judge"
)

// RuleSet identifies which rule list a policy rule belongs to.
type RuleSet string

const (
	RuleSetInput  RuleSet = "input"
	RuleSetOutput RuleSet = "output"
	RuleSetTool   RuleSet = "tool"
)

// DetectorScore mirrors the InputVerdict per-detector breakdown from input-defense.
type DetectorScore struct {
	DetectorID      string            `json:"detector_id"`
	DetectorVersion string            `json:"detector_version,omitempty"`
	Score           float64           `json:"score"`
	Reasoning       string            `json:"reasoning,omitempty"`
	LatencyMS       int64             `json:"latency_ms,omitempty"`
	Metadata        map[string]string `json:"metadata,omitempty"`
}

// InputVerdict is consumed as-is from input-defense (Stage 2 schema).
type InputVerdict struct {
	Action             string          `json:"action"`
	FusedScore         float64         `json:"fused_score"`
	DetectorScores     []DetectorScore `json:"detector_scores"`
	TransformedContent *string         `json:"transformed_content,omitempty"`
	EscalationReason   *string         `json:"escalation_reason,omitempty"`
	TotalLatencyMS     int64           `json:"total_latency_ms,omitempty"`
	RequestID          *string         `json:"request_id,omitempty"`
}

// OutputVerdict placeholder for output-defense integration (Stage 5).
type OutputVerdict struct {
	Action         string          `json:"action"`
	FusedScore     float64         `json:"fused_score"`
	DetectorScores []DetectorScore `json:"detector_scores,omitempty"`
	RedactedContent *string        `json:"redacted_content,omitempty"`
}

// ToolArgument placeholder for agent-gate integration (Stage 6).
type ToolArgument struct {
	Name                 string `json:"name"`
	TaintLevel           string `json:"taint_level,omitempty"`
	ContainsCredentials  bool   `json:"contains_credentials"`
}

// ToolCallRequest placeholder for agent-gate integration.
type ToolCallRequest struct {
	ToolName   string         `json:"tool_name"`
	RiskLevel  string         `json:"risk_level,omitempty"`
	Arguments  []ToolArgument `json:"arguments,omitempty"`
}

// PolicyRule is a single CEL rule within a policy pack.
type PolicyRule struct {
	ID          string  `yaml:"id" json:"id"`
	Name        string  `yaml:"name" json:"name"`
	CEL         string  `yaml:"cel" json:"cel"`
	Action      Action  `yaml:"action" json:"action"`
	Enabled     bool    `yaml:"enabled" json:"enabled"`
	Priority    int     `yaml:"priority,omitempty" json:"priority,omitempty"`
	TransformSpec string `yaml:"transform_spec,omitempty" json:"transform_spec,omitempty"`
}

// PolicySettings holds pack-level defaults.
type PolicySettings struct {
	ShadowMode    bool   `yaml:"shadow_mode" json:"shadow_mode"`
	DefaultAction Action `yaml:"default_action" json:"default_action"`
}

// PolicyPack is a versioned, tenant-scoped set of CEL rules.
type PolicyPack struct {
	ID          string         `yaml:"id" json:"id"`
	Version     string         `yaml:"version" json:"version"`
	TenantID    string         `yaml:"tenant_id" json:"tenant_id"`
	Description string         `yaml:"description,omitempty" json:"description,omitempty"`
	Extends     string         `yaml:"extends,omitempty" json:"extends,omitempty"`
	InputRules  []PolicyRule   `yaml:"input_rules,omitempty" json:"input_rules,omitempty"`
	OutputRules []PolicyRule   `yaml:"output_rules,omitempty" json:"output_rules,omitempty"`
	ToolRules   []PolicyRule   `yaml:"tool_rules,omitempty" json:"tool_rules,omitempty"`
	Overrides   []RuleOverride `yaml:"overrides,omitempty" json:"overrides,omitempty"`
	Settings    PolicySettings `yaml:"settings" json:"settings"`
}

// RuleOverride disables or replaces a rule from a base pack (per-tenant).
type RuleOverride struct {
	ID      string `yaml:"id" json:"id"`
	Enabled *bool  `yaml:"enabled,omitempty" json:"enabled,omitempty"`
}

// PolicyRuleMatch records an evaluated rule outcome for audit.
type PolicyRuleMatch struct {
	RuleID         string `json:"rule_id"`
	RuleName       string `json:"rule_name"`
	CELExpression  string `json:"cel_expression"`
	Matched        bool   `json:"matched"`
	MatchReason    string `json:"match_reason,omitempty"`
}

// PolicyDecision is the evaluation result returned to callers.
type PolicyDecision struct {
	Action               Action            `json:"action"`
	PolicyPackID         string            `json:"policy_pack_id"`
	PolicyPackVersion    string            `json:"policy_pack_version"`
	MatchedRules         []PolicyRuleMatch `json:"matched_rules"`
	BlockReason          string            `json:"block_reason,omitempty"`
	TransformSpec        string            `json:"transform_spec,omitempty"`
	Mode                 EvaluationMode    `json:"mode"`
	ShadowAction         Action            `json:"shadow_action,omitempty"`
	TenantID             string            `json:"tenant_id,omitempty"`
	EvaluatedAt          time.Time         `json:"evaluated_at"`
	EvaluationLatencyMS  int64             `json:"evaluation_latency_ms"`
}

// DryRunRequest evaluates draft policy YAML against a sample verdict without persisting.
type DryRunRequest struct {
	YAML     string          `json:"yaml"`
	RuleSet  string          `json:"rule_set"`
	TenantID string          `json:"tenant_id,omitempty"`
	Sample   json.RawMessage `json:"sample"`
}

// DryRunResponse returns validation or evaluation outcome for draft policy YAML.
type DryRunResponse struct {
	Valid    bool            `json:"valid"`
	Error    string          `json:"error,omitempty"`
	Decision *PolicyDecision `json:"decision,omitempty"`
}

// TraceContext correlates audit receipts across services.
type TraceContext struct {
	TraceID   string `json:"trace_id,omitempty"`
	RequestID string `json:"request_id,omitempty"`
}

// EvaluateInputRequest is the HTTP/RPC body for input policy evaluation.
type EvaluateInputRequest struct {
	InputVerdict InputVerdict   `json:"input_verdict"`
	TenantID     string         `json:"tenant_id"`
	PolicyPackID string         `json:"policy_pack_id,omitempty"`
	Mode         EvaluationMode `json:"mode,omitempty"`
	Trace        *TraceContext  `json:"trace,omitempty"`
}

// EvaluateOutputRequest evaluates output-defense verdicts.
type EvaluateOutputRequest struct {
	OutputVerdict OutputVerdict  `json:"output_verdict"`
	TenantID      string         `json:"tenant_id"`
	PolicyPackID  string         `json:"policy_pack_id,omitempty"`
	Mode          EvaluationMode `json:"mode,omitempty"`
	Trace         *TraceContext  `json:"trace,omitempty"`
}

// EvaluateToolRequest evaluates tool-call gate requests.
type EvaluateToolRequest struct {
	ToolCall     ToolCallRequest `json:"tool_call"`
	TenantID     string          `json:"tenant_id"`
	PolicyPackID string          `json:"policy_pack_id,omitempty"`
	Mode         EvaluationMode  `json:"mode,omitempty"`
}

// EvaluateResponse wraps a policy decision.
type EvaluateResponse struct {
	Decision PolicyDecision `json:"decision"`
}
