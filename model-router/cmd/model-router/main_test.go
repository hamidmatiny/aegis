package main_test

import (
	"bytes"
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
