package router_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aegis-platform/aegis/model-router/internal/config"
	"github.com/aegis-platform/aegis/model-router/internal/models"
	"github.com/aegis-platform/aegis/model-router/internal/provider"
	"github.com/aegis-platform/aegis/model-router/internal/router"
)

func TestFallbackToSecondProvider(t *testing.T) {
	failServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"error":"fail"}`))
	}))
	defer failServer.Close()

	reg := provider.NewRegistry()
	failProvider, _ := reg.Build(provider.ProviderConfig{
		ID: "openai", BaseURL: failServer.URL, Enabled: true, DefaultModel: "gpt-4o-mini",
	})
	mockProvider, _ := reg.Build(provider.ProviderConfig{ID: "mock", Enabled: true, DefaultModel: "mock-model"})

	cfg := config.Config{
		Routing: config.RoutingConfig{DefaultProvider: "openai", DefaultModel: "gpt-4o-mini"},
		Retry:   config.RetryConfig{MaxAttempts: 1, BackoffMS: 1},
	}
	cfg.Providers = map[string]config.ProviderEntry{
		"openai": {Enabled: true},
		"mock":   {Enabled: true, DefaultModel: "mock-model"},
	}
	cfg.Routing.FallbackChain = []config.RouteTarget{
		{Provider: "mock", Model: "mock-model"},
	}

	rtr := router.New(cfg, map[string]provider.Provider{
		"openai": failProvider,
		"mock":   mockProvider,
	})

	resp, err := rtr.Chat(context.Background(), models.ChatRequest{
		Model:    "gpt-4o-mini",
		Messages: []models.ChatMessage{{Role: "user", Content: "hello"}},
	})
	if err != nil {
		t.Fatalf("Chat: %v", err)
	}
	if !resp.FallbackUsed {
		t.Fatal("expected fallback to be used")
	}
	if resp.Provider != "mock" {
		t.Fatalf("expected mock provider, got %s", resp.Provider)
	}
}

func TestMockProviderChat(t *testing.T) {
	reg := provider.NewRegistry()
	p, err := reg.Build(provider.ProviderConfig{ID: "mock", Enabled: true, DefaultModel: "mock-model"})
	if err != nil {
		t.Fatal(err)
	}
	resp, err := p.Chat(context.Background(), models.ChatRequest{
		Model:    "mock-model",
		Messages: []models.ChatMessage{{Role: "user", Content: "ping"}},
	})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Content == "" {
		t.Fatal("expected content")
	}
}

func TestResolveChainDeduplicates(t *testing.T) {
	cfg := config.Config{
		Routing: config.RoutingConfig{
			DefaultProvider: "mock",
			DefaultModel:    "mock-model",
			FallbackChain: []config.RouteTarget{
				{Provider: "mock", Model: "mock-model"},
			},
		},
	}
	chain := cfg.ResolveChain("", "")
	if len(chain) != 1 {
		t.Fatalf("expected 1 target, got %d", len(chain))
	}
}
