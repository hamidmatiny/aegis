package pipeline

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/aegis-platform/aegis/gateway/internal/config"
)

// ChatRequest mirrors the OpenAI-compatible gateway chat body.
type ChatRequest struct {
	Model       string           `json:"model"`
	Messages    []map[string]any `json:"messages"`
	Provider    string           `json:"provider,omitempty"`
	Stream      bool             `json:"stream,omitempty"`
	Temperature *float64         `json:"temperature,omitempty"`
	MaxTokens   *int             `json:"max_tokens,omitempty"`
}

// ToolEvaluateRequest is the agent-gate tool evaluation body.
type ToolEvaluateRequest struct {
	ToolCall map[string]any `json:"tool_call"`
}

// Pipeline orchestrates input → policy → model-router → output → policy.
type Pipeline struct {
	cfg    config.Config
	client *http.Client
}

func New(cfg config.Config) *Pipeline {
	return &Pipeline{
		cfg: cfg,
		client: &http.Client{
			Timeout: time.Duration(cfg.HTTPTimeoutSeconds) * time.Second,
		},
	}
}

func (p *Pipeline) ChatCompletions(ctx context.Context, req ChatRequest, trace map[string]string) (map[string]any, error) {
	if req.Stream {
		return nil, &StreamingUnsupportedError{}
	}
	if req.Model == "" {
		req.Model = p.cfg.DefaultModel
	}

	userText, err := userTextFromMessages(req.Messages)
	if err != nil {
		return nil, err
	}
	if trace == nil {
		trace = newTrace()
	}

	inputResp, err := p.postJSON(ctx, p.cfg.InputDefenseURL+"/analyze", map[string]any{
		"tenant_id": p.cfg.DefaultTenantID,
		"trace":     trace,
		"text":      userText,
	})
	if err != nil {
		return nil, err
	}
	inputVerdict, _ := inputResp["verdict"].(map[string]any)
	if err := checkInputVerdict(inputVerdict); err != nil {
		return nil, err
	}

	policyIn, err := p.postJSON(ctx, p.cfg.PolicyEngineURL+"/v1/evaluate/input", map[string]any{
		"tenant_id":     p.cfg.DefaultTenantID,
		"mode":          "enforce",
		"trace":         trace,
		"input_verdict": inputVerdict,
	})
	if err != nil {
		return nil, err
	}
	if decision, ok := policyIn["decision"].(map[string]any); ok {
		if err := checkPolicyDecision(decision, "input"); err != nil {
			return nil, err
		}
	}

	routerBody := map[string]any{
		"model":    req.Model,
		"messages": req.Messages,
	}
	if req.Provider != "" {
		routerBody["provider"] = req.Provider
	}
	if req.Temperature != nil {
		routerBody["temperature"] = *req.Temperature
	}
	if req.MaxTokens != nil {
		routerBody["max_tokens"] = *req.MaxTokens
	}

	llmResp, err := p.postJSON(ctx, p.cfg.ModelRouterURL+"/v1/chat/completions", routerBody)
	if err != nil {
		if perr, ok := err.(*ProviderError); ok {
			return nil, perr
		}
		return nil, err
	}

	content, err := assistantContent(llmResp)
	if err != nil {
		return nil, err
	}

	outputResp, err := p.postJSON(ctx, p.cfg.OutputDefenseURL+"/analyze", map[string]any{
		"tenant_id":       p.cfg.DefaultTenantID,
		"trace":           trace,
		"content":         content,
		"original_prompt": userText,
	})
	if err != nil {
		return nil, err
	}
	outputVerdict, _ := outputResp["verdict"].(map[string]any)
	if err := checkOutputVerdict(outputVerdict); err != nil {
		return nil, err
	}

	policyOut, err := p.postJSON(ctx, p.cfg.PolicyEngineURL+"/v1/evaluate/output", map[string]any{
		"tenant_id":      p.cfg.DefaultTenantID,
		"mode":           "enforce",
		"trace":          trace,
		"output_verdict": outputVerdict,
	})
	if err != nil {
		return nil, err
	}
	if decision, ok := policyOut["decision"].(map[string]any); ok {
		if err := checkPolicyDecision(decision, "output"); err != nil {
			return nil, err
		}
	}

	finalContent := content
	if redacted, ok := outputVerdict["redacted_content"].(string); ok && redacted != "" {
		finalContent = redacted
	}
	setAssistantContent(llmResp, finalContent)

	aegis, _ := llmResp["aegis"].(map[string]any)
	if aegis == nil {
		aegis = map[string]any{}
		llmResp["aegis"] = aegis
	}
	aegis["trace_id"] = trace["trace_id"]
	aegis["request_id"] = trace["request_id"]
	aegis["input_verdict"] = inputVerdict
	aegis["output_verdict"] = outputVerdict
	aegis["input_policy"] = policyIn["decision"]
	aegis["output_policy"] = policyOut["decision"]

	return llmResp, nil
}

func (p *Pipeline) EvaluateTool(ctx context.Context, toolCall map[string]any, trace map[string]string) (map[string]any, error) {
	if trace == nil {
		trace = newTrace()
	}
	resp, err := p.postJSON(ctx, p.cfg.AgentGateURL+"/v1/evaluate", map[string]any{
		"tenant_id": p.cfg.DefaultTenantID,
		"mode":      "enforce",
		"trace":     trace,
		"tool_call": toolCall,
	})
	if err != nil {
		return nil, err
	}
	decision, _ := resp["decision"].(map[string]any)
	status, _ := decision["status"].(string)
	switch status {
	case "AWAITING_HUMAN_APPROVAL":
		approvalID, _ := decision["approval_request_id"].(string)
		toolName, _ := toolCall["tool_name"].(string)
		return nil, &ApprovalRequiredError{
			Message:    "Tool call requires human approval",
			ApprovalID: approvalID,
			ToolName:   toolName,
			Details:    resp,
		}
	case "DENIED":
		reason, _ := decision["denial_reason"].(string)
		if reason == "" {
			reason = "Tool call denied by agent-gate"
		}
		return nil, &PolicyBlockedError{
			Message: reason,
			Layer:   "tool_gate",
			Action:  status,
			Details: resp,
		}
	}
	aegis, _ := resp["aegis"].(map[string]any)
	if aegis == nil {
		aegis = map[string]any{}
		resp["aegis"] = aegis
	}
	aegis["trace_id"] = trace["trace_id"]
	aegis["request_id"] = trace["request_id"]
	return resp, nil
}

func (p *Pipeline) postJSON(ctx context.Context, url string, payload map[string]any) (map[string]any, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := p.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)

	if resp.StatusCode >= 400 {
		var parsed map[string]any
		_ = json.Unmarshal(raw, &parsed)
		if parsed == nil {
			parsed = map[string]any{"error": string(raw)}
		}
		if url == p.cfg.ModelRouterURL+"/v1/chat/completions" {
			return nil, providerErrorFromBody(resp.StatusCode, parsed)
		}
		errText, _ := parsed["error"].(string)
		if errText == "" {
			errText = string(raw)
		}
		return nil, &HTTPError{URL: url, StatusCode: resp.StatusCode, Body: errText}
	}

	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("decode %s: %w", url, err)
	}
	return out, nil
}

func providerErrorFromBody(statusCode int, body map[string]any) *ProviderError {
	errMsg, _ := body["error"].(string)
	aegis, _ := body["aegis"].(map[string]any)
	modelErr, _ := aegis["model_error"].(map[string]any)
	errType := "provider_error"
	if modelErr != nil {
		if t, ok := modelErr["error_type"].(string); ok && t != "" {
			errType = t
		}
	}
	provider, _ := modelErr["provider"].(string)
	model, _ := modelErr["rejected_model"].(string)
	return &ProviderError{
		Message:    errMsg,
		StatusCode: statusCode,
		Provider:   provider,
		Model:      model,
		ErrorType:  errType,
		Details:    body,
	}
}

func newTrace() map[string]string {
	return map[string]string{
		"trace_id":   randomID(),
		"request_id": randomID(),
	}
}

func randomID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func userTextFromMessages(messages []map[string]any) (string, error) {
	var parts []string
	for _, msg := range messages {
		role, _ := msg["role"].(string)
		content, _ := msg["content"].(string)
		if role == "user" && content != "" {
			parts = append(parts, content)
		}
	}
	if len(parts) == 0 {
		return "", fmt.Errorf("messages must include at least one user message")
	}
	return joinParts(parts), nil
}

func joinParts(parts []string) string {
	out := parts[0]
	for i := 1; i < len(parts); i++ {
		out += "\n\n" + parts[i]
	}
	return out
}

func assistantContent(llmResp map[string]any) (string, error) {
	choices, ok := llmResp["choices"].([]any)
	if !ok || len(choices) == 0 {
		return "", fmt.Errorf("model-router response missing choices")
	}
	choice, ok := choices[0].(map[string]any)
	if !ok {
		return "", fmt.Errorf("invalid choice shape")
	}
	message, ok := choice["message"].(map[string]any)
	if !ok {
		return "", fmt.Errorf("invalid message shape")
	}
	content, _ := message["content"].(string)
	return content, nil
}

func setAssistantContent(llmResp map[string]any, content string) {
	choices, ok := llmResp["choices"].([]any)
	if !ok || len(choices) == 0 {
		return
	}
	choice, ok := choices[0].(map[string]any)
	if !ok {
		return
	}
	message, ok := choice["message"].(map[string]any)
	if !ok {
		message = map[string]any{}
		choice["message"] = message
	}
	message["content"] = content
}

func checkInputVerdict(verdict map[string]any) error {
	action, _ := verdict["action"].(string)
	if action == "BLOCK" {
		score, _ := verdict["fused_score"].(float64)
		return &PolicyBlockedError{
			Message:    "Input blocked by input-defense",
			Layer:      "input_defense",
			Action:     action,
			FusedScore: score,
			Details:    map[string]any{"input_verdict": verdict},
		}
	}
	return nil
}

func checkOutputVerdict(verdict map[string]any) error {
	action, _ := verdict["action"].(string)
	if action == "BLOCK" {
		score, _ := verdict["fused_score"].(float64)
		return &PolicyBlockedError{
			Message:    "Output blocked by output-defense",
			Layer:      "output_defense",
			Action:     action,
			FusedScore: score,
			Details:    map[string]any{"output_verdict": verdict},
		}
	}
	return nil
}

func checkPolicyDecision(decision map[string]any, layer string) error {
	action, _ := decision["action"].(string)
	if action == "block" {
		reason, _ := decision["block_reason"].(string)
		if reason == "" {
			reason = fmt.Sprintf("Blocked by policy (%s)", layer)
		}
		return &PolicyBlockedError{
			Message:      reason,
			Layer:        "policy_" + layer,
			PolicyAction: action,
			Details:      map[string]any{"policy_decision": decision},
		}
	}
	return nil
}
