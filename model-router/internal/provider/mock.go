package provider

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/aegis-platform/aegis/model-router/internal/models"
)

// Mock provides deterministic responses for dev/test without upstream API keys.
type Mock struct {
	cfg ProviderConfig
}

func NewMock(cfg ProviderConfig) (Provider, error) {
	if cfg.DefaultModel == "" {
		cfg.DefaultModel = "mock-model"
	}
	return &Mock{cfg: cfg}, nil
}

func (p *Mock) ID() string { return "mock" }

func (p *Mock) Ping(_ context.Context) error { return nil }

func (p *Mock) Chat(_ context.Context, req models.ChatRequest) (*models.ChatResponse, error) {
	content := p.echo(req)
	return &models.ChatResponse{
		ID:           "mock-" + fmt.Sprintf("%d", time.Now().UnixNano()),
		Provider:     p.cfg.ID,
		Model:        pickModel(req, p.cfg.DefaultModel),
		Content:      content,
		FinishReason: "stop",
		Usage:        models.Usage{PromptTokens: 10, CompletionTokens: len(content), TotalTokens: 10 + len(content)},
		CreatedAt:    time.Now().UTC(),
	}, nil
}

func (p *Mock) ChatStream(_ context.Context, req models.ChatRequest) (<-chan models.StreamChunk, error) {
	content := p.echo(req)
	out := make(chan models.StreamChunk, 8)
	go func() {
		defer close(out)
		words := strings.Split(content, " ")
		for _, w := range words {
			out <- models.StreamChunk{
				Provider: p.cfg.ID,
				Model:    pickModel(req, p.cfg.DefaultModel),
				Delta:    w + " ",
			}
		}
		out <- models.StreamChunk{Done: true, Provider: p.cfg.ID, Model: pickModel(req, p.cfg.DefaultModel)}
	}()
	return out, nil
}

func (p *Mock) echo(req models.ChatRequest) string {
	if len(req.Messages) == 0 {
		return "mock response"
	}
	last := req.Messages[len(req.Messages)-1].Content
	return fmt.Sprintf("[mock:%s] %s", pickModel(req, p.cfg.DefaultModel), last)
}

func pickModel(req models.ChatRequest, fallback string) string {
	if req.Model != "" {
		return req.Model
	}
	return fallback
}
