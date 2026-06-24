package router_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"slices"
	"strings"
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

func TestFallbackToGrokProvider(t *testing.T) {
	grokCalled := false
	grokServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/completions" {
			t.Errorf("grok: unexpected path %s", r.URL.Path)
		}
		grokCalled = true
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"id":    "grok-resp-1",
			"model": "grok-4.3",
			"choices": []map[string]any{{
				"message":       map[string]string{"content": "hello from grok"},
				"finish_reason": "stop",
			}},
		})
	}))
	defer grokServer.Close()

	failServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"error":"fail"}`))
	}))
	defer failServer.Close()

	reg := provider.NewRegistry()
	failProvider, err := reg.Build(provider.ProviderConfig{
		ID: "openai", BaseURL: failServer.URL, Enabled: true, DefaultModel: "gpt-4o-mini",
	})
	if err != nil {
		t.Fatal(err)
	}
	grokProvider, err := reg.Build(provider.ProviderConfig{
		ID: "grok", BaseURL: grokServer.URL, Enabled: true, DefaultModel: "grok-4.3",
	})
	if err != nil {
		t.Fatal(err)
	}

	cfg := config.Config{
		Routing: config.RoutingConfig{DefaultProvider: "openai", DefaultModel: "gpt-4o-mini"},
		Retry:   config.RetryConfig{MaxAttempts: 1, BackoffMS: 1},
	}
	cfg.Providers = map[string]config.ProviderEntry{
		"openai": {Enabled: true},
		"grok":   {Enabled: true, DefaultModel: "grok-4.3"},
	}
	cfg.Routing.FallbackChain = []config.RouteTarget{
		{Provider: "grok", Model: "grok-4.3"},
	}

	rtr := router.New(cfg, map[string]provider.Provider{
		"openai": failProvider,
		"grok":   grokProvider,
	})

	resp, err := rtr.Chat(context.Background(), models.ChatRequest{
		Model:    "gpt-4o-mini",
		Messages: []models.ChatMessage{{Role: "user", Content: "hello"}},
	})
	if err != nil {
		t.Fatalf("Chat: %v", err)
	}
	if !grokCalled {
		t.Fatal("expected grok HTTP handler to be invoked")
	}
	if !resp.FallbackUsed {
		t.Fatal("expected fallback to be used")
	}
	if resp.Provider != "grok" {
		t.Fatalf("expected grok provider, got %s", resp.Provider)
	}
	if !slices.Contains(resp.AttemptedProviders, "openai") {
		t.Fatalf("attempted_providers missing openai: %v", resp.AttemptedProviders)
	}
	if !slices.Contains(resp.AttemptedProviders, "grok") {
		t.Fatalf("attempted_providers missing grok: %v", resp.AttemptedProviders)
	}
}

func TestModelRetiredDoesNotFallbackToMock(t *testing.T) {
	retiredServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"code":"invalid-argument","error":"Model not found"}`))
	}))
	defer retiredServer.Close()

	reg := provider.NewRegistry()
	grokProvider, err := reg.Build(provider.ProviderConfig{
		ID: "grok", BaseURL: retiredServer.URL, Enabled: true, DefaultModel: "grok-2-latest",
	})
	if err != nil {
		t.Fatal(err)
	}
	mockProvider, err := reg.Build(provider.ProviderConfig{ID: "mock", Enabled: true, DefaultModel: "mock-model"})
	if err != nil {
		t.Fatal(err)
	}

	cfg := config.Config{
		Routing: config.RoutingConfig{DefaultProvider: "grok", DefaultModel: "grok-2-latest"},
		Retry:   config.RetryConfig{MaxAttempts: 1, BackoffMS: 1},
	}
	cfg.Providers = map[string]config.ProviderEntry{
		"grok": {Enabled: true, DefaultModel: "grok-2-latest"},
		"mock": {Enabled: true, DefaultModel: "mock-model"},
	}
	cfg.Routing.FallbackChain = []config.RouteTarget{
		{Provider: "mock", Model: "mock-model"},
	}

	rtr := router.New(cfg, map[string]provider.Provider{
		"grok": grokProvider,
		"mock": mockProvider,
	})

	_, err = rtr.Chat(context.Background(), models.ChatRequest{
		Provider: "grok",
		Model:    "grok-2-latest",
		Messages: []models.ChatMessage{{Role: "user", Content: "hello"}},
	})
	if err == nil {
		t.Fatal("expected model retired error")
	}
	modelErr, ok := provider.AsModelRetiredError(err)
	if !ok {
		t.Fatalf("expected ModelRetiredError, got %T: %v", err, err)
	}
	if modelErr.RejectedModel != "grok-2-latest" {
		t.Fatalf("unexpected rejected model: %s", modelErr.RejectedModel)
	}
	if !strings.Contains(modelErr.Guidance(), "providers.yaml") {
		t.Fatalf("guidance should mention providers.yaml: %s", modelErr.Guidance())
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
