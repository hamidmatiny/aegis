package provider

import (
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

// ModelRetiredError indicates the upstream rejected the configured model ID.
// This is distinct from transient failures and must not trigger silent fallback.
type ModelRetiredError struct {
	Provider      string
	RejectedModel string
	UpstreamBody  string
	StatusCode    int
}

func (e *ModelRetiredError) Error() string {
	return fmt.Sprintf(
		"provider %q rejected model %q: %s",
		e.Provider,
		e.RejectedModel,
		e.Guidance(),
	)
}

// Guidance returns a human-readable remediation message for operators.
func (e *ModelRetiredError) Guidance() string {
	return fmt.Sprintf(
		"Model %q on provider %q was rejected as not found. This usually means the model has been retired or renamed. Update model-router/config/providers.yaml with a current model ID for this provider — check the provider's official model list/docs for the latest available model.",
		e.RejectedModel,
		e.Provider,
	)
}

// ErrorType is the stable API label for this failure class.
func (e *ModelRetiredError) ErrorType() string {
	return "model_retired"
}

// AsModelRetiredError unwraps a ModelRetiredError from an error chain.
func AsModelRetiredError(err error) (*ModelRetiredError, bool) {
	var target *ModelRetiredError
	if errors.As(err, &target) {
		return target, true
	}
	return nil, false
}

// IsModelRetiredError reports whether err is a model-not-found failure.
func IsModelRetiredError(err error) bool {
	_, ok := AsModelRetiredError(err)
	return ok
}

// classifyUpstreamError maps HTTP error bodies to AuthError, ModelRetiredError, or UpstreamError.
func classifyUpstreamError(providerID, model, apiKeyEnv string, status int, body string) error {
	if isAuthFailure(status, body) {
		return &AuthError{
			Provider:  providerID,
			Status:    status,
			Body:      body,
			APIKeyEnv: apiKeyEnv,
		}
	}
	if isModelNotFound(providerID, status, body) {
		return &ModelRetiredError{
			Provider:      providerID,
			RejectedModel: model,
			UpstreamBody:  body,
			StatusCode:    status,
		}
	}
	return &UpstreamError{Provider: providerID, Status: status, Body: body}
}

func isModelNotFound(providerID string, status int, body string) bool {
	lower := strings.ToLower(body)

	// OpenAI-compatible (OpenAI, Grok/xAI, Ollama, vLLM)
	if strings.Contains(lower, "model_not_found") {
		return true
	}
	if strings.Contains(lower, "model not found") {
		return true
	}
	if strings.Contains(lower, "invalid-argument") && strings.Contains(lower, "model") {
		return true
	}
	if strings.Contains(lower, "does not exist") && strings.Contains(lower, "model") {
		return true
	}
	if strings.Contains(lower, "unknown model") {
		return true
	}
	if strings.Contains(lower, "model_retired") || strings.Contains(lower, "model retired") {
		return true
	}

	// Anthropic
	if strings.Contains(lower, `"type":"not_found_error"`) || strings.Contains(lower, `"type": "not_found_error"`) {
		if strings.Contains(lower, "model") {
			return true
		}
	}

	// Gemini
	if strings.Contains(lower, `"code":404`) || strings.Contains(lower, `"code": 404`) {
		if strings.Contains(lower, "model") {
			return true
		}
	}
	if strings.Contains(lower, "not found") && strings.Contains(lower, "models/") {
		return true
	}

	// Provider-specific fallbacks for common 404-shaped model errors
	if status == 404 && strings.Contains(lower, "model") {
		return true
	}
	if providerID == "grok" && status == 400 && strings.Contains(lower, "model") {
		return true
	}

	// Structured OpenAI error object
	var openAIErr struct {
		Error struct {
			Code    string `json:"code"`
			Type    string `json:"type"`
			Message string `json:"message"`
		} `json:"error"`
	}
	if json.Unmarshal([]byte(body), &openAIErr) == nil {
		code := strings.ToLower(openAIErr.Error.Code)
		typ := strings.ToLower(openAIErr.Error.Type)
		msg := strings.ToLower(openAIErr.Error.Message)
		if code == "model_not_found" || typ == "invalid_request_error" && strings.Contains(msg, "model") && strings.Contains(msg, "not found") {
			return true
		}
	}

	return false
}

func modelFromRequest(reqModel, defaultModel string) string {
	if reqModel != "" {
		return reqModel
	}
	return defaultModel
}
