package policy

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/aegis-platform/aegis/agent-gate/internal/models"
)

// Client calls policy-engine tool evaluation.
type Client struct {
	baseURL    string
	httpClient *http.Client
}

func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

func (c *Client) EvaluateTool(
	ctx context.Context,
	req models.PolicyEvaluateToolRequest,
) (*models.PolicyDecision, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	httpReq, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		c.baseURL+"/v1/evaluate/tool",
		bytes.NewReader(body),
	)
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("policy-engine request failed: %w", err)
	}
	defer resp.Body.Close()

	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("policy-engine returned %d: %s", resp.StatusCode, string(raw))
	}

	var parsed models.PolicyEvaluateResponse
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, err
	}
	return &parsed.Decision, nil
}

// ToPolicyToolCall converts a sanitized gate request for policy CEL evaluation.
func ToPolicyToolCall(call models.ToolCallRequest) models.PolicyToolCallRequest {
	args := make([]models.PolicyToolArgument, len(call.Arguments))
	for i, a := range call.Arguments {
		args[i] = models.PolicyToolArgument{
			Name:                a.Name,
			TaintLevel:          a.TaintLevel,
			ContainsCredentials: a.ContainsCredentials,
		}
	}
	return models.PolicyToolCallRequest{
		ToolName:  call.ToolName,
		RiskLevel: call.RiskLevel,
		Arguments: args,
	}
}
