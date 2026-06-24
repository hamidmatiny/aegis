package models

import (
	"encoding/json"
	"time"
)

// Event types align with shared/jsonschema/v1/audit_receipt.json.
const (
	EventInputDefense   = "INPUT_DEFENSE"
	EventPolicyDecision = "POLICY_DECISION"
	EventOutputDefense  = "OUTPUT_DEFENSE"
	EventToolGate       = "TOOL_GATE"
	EventModelRouter    = "MODEL_ROUTER"
	EventRedteam        = "REDTEAM"
)

var ValidEventTypes = map[string]struct{}{
	EventInputDefense:   {},
	EventPolicyDecision: {},
	EventOutputDefense:  {},
	EventToolGate:       {},
	EventModelRouter:    {},
	EventRedteam:        {},
}

type TraceContext struct {
	TraceID   string `json:"trace_id,omitempty"`
	RequestID string `json:"request_id,omitempty"`
}

type WriteReceiptRequest struct {
	EventType         string          `json:"event_type"`
	TenantID          string          `json:"tenant_id"`
	Trace             *TraceContext   `json:"trace,omitempty"`
	InputVerdict      json.RawMessage `json:"input_verdict,omitempty"`
	PolicyDecision    json.RawMessage `json:"policy_decision,omitempty"`
	OutputVerdict     json.RawMessage `json:"output_verdict,omitempty"`
	ToolDecision      json.RawMessage `json:"tool_decision,omitempty"`
	PolicyPackID      string          `json:"policy_pack_id,omitempty"`
	PolicyPackVersion string          `json:"policy_pack_version,omitempty"`
	Metadata          json.RawMessage `json:"metadata,omitempty"`
}

type Receipt struct {
	ReceiptID         string          `json:"receipt_id"`
	EventType         string          `json:"event_type"`
	TenantID          string          `json:"tenant_id"`
	Trace             *TraceContext   `json:"trace,omitempty"`
	InputVerdict      json.RawMessage `json:"input_verdict,omitempty"`
	PolicyDecision    json.RawMessage `json:"policy_decision,omitempty"`
	OutputVerdict     json.RawMessage `json:"output_verdict,omitempty"`
	ToolDecision      json.RawMessage `json:"tool_decision,omitempty"`
	PolicyPackID      string          `json:"policy_pack_id,omitempty"`
	PolicyPackVersion string          `json:"policy_pack_version,omitempty"`
	Metadata          json.RawMessage `json:"metadata,omitempty"`
	CreatedAt         time.Time       `json:"created_at"`
	SignerKeyID       string          `json:"signer_key_id"`
	Signature         []byte          `json:"signature"`
	PayloadHash       []byte          `json:"payload_hash"`
}

type WriteReceiptResponse struct {
	ReceiptID string `json:"receipt_id"`
	Persisted bool   `json:"persisted"`
	Receipt   Receipt `json:"receipt"`
}

type QueryRequest struct {
	TenantID  string
	EventType string
	StartTime *time.Time
	EndTime   *time.Time
	Limit     int
	Cursor    string
}

type QueryResponse struct {
	Receipts   []Receipt `json:"receipts"`
	NextCursor string    `json:"next_cursor,omitempty"`
}

type VerifyResponse struct {
	ReceiptID string `json:"receipt_id"`
	Valid     bool   `json:"valid"`
	Reason    string `json:"reason,omitempty"`
}

type ExportRequest struct {
	TenantID  string
	StartTime *time.Time
	EndTime   *time.Time
	Format    string
}
