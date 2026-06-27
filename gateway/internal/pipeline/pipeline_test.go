package pipeline_test

import (
	"context"
	"errors"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aegis-platform/aegis/gateway/internal/config"
	"github.com/aegis-platform/aegis/gateway/internal/pipeline"
)

func TestChatCompletionsHappyPath(t *testing.T) {
	input := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"verdict": map[string]any{"action": "ALLOW", "fused_score": 0.1},
		})
	}))
	defer input.Close()

	policy := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"decision": map[string]any{"action": "allow"},
		})
	}))
	defer policy.Close()

	router := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"object": "chat.completion",
			"choices": []any{
				map[string]any{"message": map[string]any{"content": "hello"}},
			},
		})
	}))
	defer router.Close()

	output := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"verdict": map[string]any{"action": "ALLOW", "fused_score": 0.1},
		})
	}))
	defer output.Close()

	p := pipeline.New(config.Config{
		InputDefenseURL:  input.URL,
		OutputDefenseURL: output.URL,
		PolicyEngineURL:  policy.URL,
		ModelRouterURL:   router.URL,
		DefaultModel:     "mock-model",
		HTTPTimeoutSeconds: 5,
	})

	resp, err := p.ChatCompletions(context.Background(), pipeline.ChatRequest{
		Model: "mock-model",
		Messages: []map[string]any{
			{"role": "user", "content": "Hello"},
		},
	}, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	aegis, ok := resp["aegis"].(map[string]any)
	if !ok {
		t.Fatal("expected aegis metadata")
	}
	if aegis["input_verdict"] == nil || aegis["output_verdict"] == nil {
		t.Fatal("expected verdict metadata in aegis block")
	}
}

func TestChatCompletionsBlocksInput(t *testing.T) {
	input := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"verdict": map[string]any{"action": "BLOCK", "fused_score": 0.99},
		})
	}))
	defer input.Close()

	p := pipeline.New(config.Config{
		InputDefenseURL:    input.URL,
		HTTPTimeoutSeconds: 5,
	})

	_, err := p.ChatCompletions(context.Background(), pipeline.ChatRequest{
		Model: "mock-model",
		Messages: []map[string]any{
			{"role": "user", "content": "attack"},
		},
	}, nil)
	if err == nil {
		t.Fatal("expected block error")
	}
	var blocked *pipeline.PolicyBlockedError
	if !errors.As(err, &blocked) {
		t.Fatalf("expected PolicyBlockedError, got %T", err)
	}
	if blocked.Layer != "input_defense" {
		t.Fatalf("unexpected layer: %s", blocked.Layer)
	}
}

func TestStreamingUnsupported(t *testing.T) {
	p := pipeline.New(config.Config{})
	_, err := p.ChatCompletions(context.Background(), pipeline.ChatRequest{
		Stream: true,
		Messages: []map[string]any{
			{"role": "user", "content": "hi"},
		},
	}, nil)
	var streaming *pipeline.StreamingUnsupportedError
	if !errors.As(err, &streaming) {
		t.Fatalf("expected StreamingUnsupportedError, got %T", err)
	}
}
