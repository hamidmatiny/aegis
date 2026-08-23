package main_test

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/aegis-platform/aegis/model-router/internal/api"
	"github.com/aegis-platform/aegis/model-router/internal/config"
	"github.com/aegis-platform/aegis/model-router/internal/models"
	"github.com/aegis-platform/aegis/model-router/internal/provider"
	"github.com/aegis-platform/aegis/model-router/internal/router"
)

func TestChatCompletionsEndpoint(t *testing.T) {
	cfgPath := filepath.Join("..", "..", "config", "providers.yaml")
	cfg, err := config.Load(cfgPath)
	if err != nil {
		t.Fatalf("Load config: %v", err)
	}
	reg := provider.NewRegistry()
	providers, err := cfg.BuildRegistry(reg)
	if err != nil {
		t.Fatalf("BuildRegistry: %v", err)
	}
	rtr := router.New(cfg, providers)
	srv := api.NewServer(rtr)
	mux := http.NewServeMux()
	srv.Register(mux)

	body, _ := json.Marshal(models.ChatRequest{
		Messages: []models.ChatMessage{{Role: "user", Content: "Hello"}},
	})
	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
	}
	var resp map[string]any
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatal(err)
	}
	if resp["object"] != "chat.completion" {
		t.Fatalf("unexpected object: %v", resp["object"])
	}
}

func TestStreamCompletions(t *testing.T) {
	cfg, err := config.Load(filepath.Join("..", "..", "config", "providers.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	reg := provider.NewRegistry()
	providers, err := cfg.BuildRegistry(reg)
	if err != nil {
		t.Fatal(err)
	}
	rtr := router.New(cfg, providers)
	srv := api.NewServer(rtr)
	mux := http.NewServeMux()
	srv.Register(mux)

	body, _ := json.Marshal(models.ChatRequest{
		Stream:   true,
		Messages: []models.ChatMessage{{Role: "user", Content: "stream test"}},
	})
	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "text/event-stream" {
		t.Fatalf("expected event-stream, got %s", ct)
	}
	if !bytes.Contains(rec.Body.Bytes(), []byte("[DONE]")) {
		t.Fatal("expected DONE marker in stream")
	}
}

func TestEmbeddingsMock(t *testing.T) {
	mux := testMux(t)
	body, _ := json.Marshal(map[string]any{
		"model": "mock-embedding",
		"input": "test",
	})
	req := httptest.NewRequest(http.MethodPost, "/v1/embeddings", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
	}
	var resp map[string]any
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatal(err)
	}
	if resp["object"] != "list" {
		t.Fatalf("object=%v", resp["object"])
	}
	data, ok := resp["data"].([]any)
	if !ok || len(data) != 1 {
		t.Fatalf("data=%v", resp["data"])
	}
	row := data[0].(map[string]any)
	emb := row["embedding"].([]any)
	if len(emb) != provider.MockEmbeddingDims {
		t.Fatalf("dims=%d", len(emb))
	}
}

func TestEmbeddingsAnthropicNotSupported(t *testing.T) {
	mux := testMux(t)
	body, _ := json.Marshal(map[string]any{
		"provider": "anthropic",
		"input":    "test",
	})
	req := httptest.NewRequest(http.MethodPost, "/v1/embeddings", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
	}
	var resp map[string]any
	_ = json.NewDecoder(rec.Body).Decode(&resp)
	aegis, _ := resp["aegis"].(map[string]any)
	me, _ := aegis["model_error"].(map[string]any)
	if me["error_type"] != "embeddings_not_supported" {
		t.Fatalf("error_type=%v", me["error_type"])
	}
}

func TestEmbeddingsGrokNotSupported(t *testing.T) {
	mux := testMux(t)
	body, _ := json.Marshal(map[string]any{
		"provider": "grok",
		"input":    "test",
	})
	req := httptest.NewRequest(http.MethodPost, "/v1/embeddings", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
	}
}

func TestEmbeddingsOpenAILiveOptional(t *testing.T) {
	if testing.Short() {
		t.Skip("short")
	}
	key := ""
	// Resolve via the same env pattern as production.
	p, err := provider.NewOpenAICompat(provider.ProviderConfig{
		ID:                    "openai",
		BaseURL:               "https://api.openai.com/v1",
		APIKeyEnv:             "OPENAI_API_KEY",
		SupportsEmbeddings:    true,
		DefaultEmbeddingModel: "text-embedding-3-small",
	})
	if err != nil {
		t.Fatal(err)
	}
	key = provider.ResolveAPIKey(provider.ProviderConfig{APIKeyEnv: "OPENAI_API_KEY"})
	if key == "" {
		t.Skip("OPENAI_API_KEY not set")
	}
	ep := p.(provider.EmbeddingProvider)
	resp, err := ep.Embed(context.Background(), models.EmbeddingRequest{
		Model: "text-embedding-3-small",
		Input: models.EmbeddingInput{Texts: []string{"aegis embeddings smoke"}},
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(resp.Data) != 1 || len(resp.Data[0].Embedding) < 8 {
		t.Fatalf("unexpected embedding: %+v", resp)
	}
}

func testMux(t *testing.T) *http.ServeMux {
	t.Helper()
	cfg, err := config.Load(filepath.Join("..", "..", "config", "providers.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	reg := provider.NewRegistry()
	providers, err := cfg.BuildRegistry(reg)
	if err != nil {
		t.Fatal(err)
	}
	rtr := router.New(cfg, providers)
	srv := api.NewServer(rtr)
	mux := http.NewServeMux()
	srv.Register(mux)
	return mux
}
