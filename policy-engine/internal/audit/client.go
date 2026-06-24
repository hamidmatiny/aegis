package audit

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"time"

	"github.com/aegis-platform/aegis/policy-engine/internal/models"
)

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

func (c *Client) EmitPolicyDecision(
	tenantID string,
	trace *models.TraceContext,
	decision models.PolicyDecision,
) {
	if !c.enabled {
		return
	}
	decisionJSON, err := json.Marshal(decision)
	if err != nil {
		slog.Warn("audit marshal policy decision failed", "error", err)
		return
	}
	payload := map[string]any{
		"event_type":          "POLICY_DECISION",
		"tenant_id":           tenantID,
		"policy_decision":     json.RawMessage(decisionJSON),
		"policy_pack_id":      decision.PolicyPackID,
		"policy_pack_version": decision.PolicyPackVersion,
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
