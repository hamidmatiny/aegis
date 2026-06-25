package provider

import (
	"context"

	"github.com/aegis-platform/aegis/model-router/internal/models"
)

// Provider abstracts an LLM upstream behind a unified interface.
type Provider interface {
	ID() string
	Chat(ctx context.Context, req models.ChatRequest) (*models.ChatResponse, error)
	ChatStream(ctx context.Context, req models.ChatRequest) (<-chan models.StreamChunk, error)
	Ping(ctx context.Context) error
}

// Factory constructs a provider from runtime configuration.
type Factory func(cfg ProviderConfig) (Provider, error)

// RouteTarget is one provider/model pair in a fallback chain.
type RouteTarget struct {
	Provider string
	Model    string
}

// ProviderConfig holds connection settings for a single upstream.
type ProviderConfig struct {
	ID           string
	BaseURL      string
	APIKey       string
	APIKeyEnv    string
	Enabled      bool
	DefaultModel string
	ExtraHeaders map[string]string
}

// Registry holds provider factories keyed by provider ID.
type Registry struct {
	factories map[string]Factory
}

func NewRegistry() *Registry {
	r := &Registry{factories: make(map[string]Factory)}
	r.Register("openai", NewOpenAICompat)
	r.Register("vllm", NewOpenAICompat)
	r.Register("ollama", NewOpenAICompat)
	r.Register("grok", NewOpenAICompat)
	r.Register("anthropic", NewAnthropic)
	r.Register("gemini", NewGemini)
	r.Register("mock", NewMock)
	return r
}

func (r *Registry) Register(id string, factory Factory) {
	r.factories[id] = factory
}

func (r *Registry) Build(cfg ProviderConfig) (Provider, error) {
	factory, ok := r.factories[cfg.ID]
	if !ok {
		return nil, &UnknownProviderError{ID: cfg.ID}
	}
	return factory(cfg)
}

// UnknownProviderError is returned when no factory is registered.
type UnknownProviderError struct {
	ID string
}

func (e *UnknownProviderError) Error() string {
	return "unknown provider: " + e.ID
}
