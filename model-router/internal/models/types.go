package models

import "time"

// ChatMessage is a unified message across all providers.
type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ChatRequest is the provider-agnostic completion request.
type ChatRequest struct {
	Provider        string            `json:"provider,omitempty"`
	Model           string            `json:"model"`
	Messages        []ChatMessage     `json:"messages"`
	Temperature     *float64          `json:"temperature,omitempty"`
	MaxTokens       *int              `json:"max_tokens,omitempty"`
	Stream          bool              `json:"stream,omitempty"`
	ProviderOptions map[string]string `json:"provider_options,omitempty"`
}

// Usage reports token consumption when available from upstream.
type Usage struct {
	PromptTokens     int `json:"prompt_tokens,omitempty"`
	CompletionTokens int `json:"completion_tokens,omitempty"`
	TotalTokens      int `json:"total_tokens,omitempty"`
}

// ChatResponse is the unified non-streaming completion response.
type ChatResponse struct {
	ID               string    `json:"id"`
	Provider         string    `json:"provider"`
	Model            string    `json:"model"`
	Content          string    `json:"content"`
	FinishReason     string    `json:"finish_reason,omitempty"`
	Usage            Usage     `json:"usage,omitempty"`
	FallbackUsed     bool      `json:"fallback_used,omitempty"`
	AttemptedProviders []string `json:"attempted_providers,omitempty"`
	CreatedAt        time.Time `json:"created_at"`
}

// StreamChunk is a unified streaming delta.
type StreamChunk struct {
	ID           string `json:"id,omitempty"`
	Provider     string `json:"provider,omitempty"`
	Model        string `json:"model,omitempty"`
	Delta        string `json:"delta,omitempty"`
	FinishReason string `json:"finish_reason,omitempty"`
	Done         bool   `json:"done,omitempty"`
}

// ProviderInfo describes a registered upstream provider.
type ProviderInfo struct {
	ID      string `json:"id"`
	Enabled bool   `json:"enabled"`
	BaseURL string `json:"base_url,omitempty"`
	Healthy bool   `json:"healthy"`
}

// RouteAttempt records a provider invocation during fallback routing.
type RouteAttempt struct {
	Provider string
	Model    string
	Err      error
}

// RouterError indicates all providers in the chain failed.
type RouterError struct {
	Message  string
	Attempts []RouteAttempt
}

func (e *RouterError) Error() string {
	return e.Message
}
