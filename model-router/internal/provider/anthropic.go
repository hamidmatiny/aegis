package provider

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/aegis-platform/aegis/model-router/internal/models"
)

// Anthropic implements the Anthropic Messages API.
type Anthropic struct {
	cfg    ProviderConfig
	client *http.Client
}

func NewAnthropic(cfg ProviderConfig) (Provider, error) {
	base := strings.TrimRight(cfg.BaseURL, "/")
	if base == "" {
		base = "https://api.anthropic.com/v1"
	}
	cfg.BaseURL = base
	return &Anthropic{cfg: cfg, client: &http.Client{Timeout: 120 * time.Second}}, nil
}

func (p *Anthropic) ID() string { return p.cfg.ID }

func (p *Anthropic) Ping(ctx context.Context) error {
	if ResolveAPIKey(p.cfg) == "" {
		return fmt.Errorf("anthropic: missing API key")
	}
	return nil
}

func (p *Anthropic) Chat(ctx context.Context, req models.ChatRequest) (*models.ChatResponse, error) {
	body, err := json.Marshal(p.buildPayload(req, 1024))
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, p.cfg.BaseURL+"/messages", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	p.applyHeaders(httpReq)
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := p.client.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, classifyUpstreamError(p.cfg.ID, modelFromRequest(req.Model, p.cfg.DefaultModel), p.cfg.APIKeyEnv, resp.StatusCode, string(raw))
	}

	var parsed anthropicResponse
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, err
	}
	content := ""
	for _, block := range parsed.Content {
		if block.Type == "text" {
			content += block.Text
		}
	}
	return &models.ChatResponse{
		ID:           parsed.ID,
		Provider:     p.cfg.ID,
		Model:        parsed.Model,
		Content:      content,
		FinishReason: parsed.StopReason,
		Usage: models.Usage{
			PromptTokens:     parsed.Usage.InputTokens,
			CompletionTokens: parsed.Usage.OutputTokens,
			TotalTokens:      parsed.Usage.InputTokens + parsed.Usage.OutputTokens,
		},
		CreatedAt: time.Now().UTC(),
	}, nil
}

func (p *Anthropic) ChatStream(ctx context.Context, req models.ChatRequest) (<-chan models.StreamChunk, error) {
	maxTokens := 1024
	if req.MaxTokens != nil {
		maxTokens = *req.MaxTokens
	}
	body, err := json.Marshal(p.buildPayload(req, maxTokens))
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, p.cfg.BaseURL+"/messages", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	p.applyHeaders(httpReq)
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "text/event-stream")

	resp, err := p.client.Do(httpReq)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		raw, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		return nil, classifyUpstreamError(p.cfg.ID, modelFromRequest(req.Model, p.cfg.DefaultModel), p.cfg.APIKeyEnv, resp.StatusCode, string(raw))
	}

	out := make(chan models.StreamChunk, 16)
	go func() {
		defer close(out)
		defer resp.Body.Close()
		dec := json.NewDecoder(resp.Body)
		for {
			var event anthropicStreamEvent
			if err := dec.Decode(&event); err != nil {
				if err == io.EOF {
					out <- models.StreamChunk{Done: true, Provider: p.cfg.ID, Model: req.Model}
				}
				return
			}
			switch event.Type {
			case "content_block_delta":
				out <- models.StreamChunk{
					Provider: p.cfg.ID,
					Model:    req.Model,
					Delta:    event.Delta.Text,
				}
			case "message_stop":
				out <- models.StreamChunk{Done: true, Provider: p.cfg.ID, Model: req.Model}
				return
			}
		}
	}()
	return out, nil
}

func (p *Anthropic) buildPayload(req models.ChatRequest, maxTokens int) map[string]any {
	model := req.Model
	if model == "" {
		model = p.cfg.DefaultModel
	}
	if req.MaxTokens != nil {
		maxTokens = *req.MaxTokens
	}
	var system string
	var messages []map[string]string
	for _, m := range req.Messages {
		if m.Role == "system" {
			system += m.Content + "\n"
			continue
		}
		role := m.Role
		if role == "assistant" {
			role = "assistant"
		} else {
			role = "user"
		}
		messages = append(messages, map[string]string{"role": role, "content": m.Content})
	}
	payload := map[string]any{
		"model":      model,
		"max_tokens": maxTokens,
		"messages":   messages,
		"stream":     req.Stream,
	}
	if system != "" {
		payload["system"] = strings.TrimSpace(system)
	}
	if req.Temperature != nil {
		payload["temperature"] = *req.Temperature
	}
	return payload
}

func (p *Anthropic) applyHeaders(req *http.Request) {
	req.Header.Set("x-api-key", ResolveAPIKey(p.cfg))
	req.Header.Set("anthropic-version", "2023-06-01")
	for k, v := range p.cfg.ExtraHeaders {
		req.Header.Set(k, v)
	}
}

type anthropicResponse struct {
	ID         string `json:"id"`
	Model      string `json:"model"`
	StopReason string `json:"stop_reason"`
	Content    []struct {
		Type string `json:"type"`
		Text string `json:"text"`
	} `json:"content"`
	Usage struct {
		InputTokens  int `json:"input_tokens"`
		OutputTokens int `json:"output_tokens"`
	} `json:"usage"`
}

type anthropicStreamEvent struct {
	Type  string `json:"type"`
	Delta struct {
		Text string `json:"text"`
	} `json:"delta"`
}

// CheckModel sends a minimal message to verify the model ID is accepted.
func (p *Anthropic) CheckModel(ctx context.Context, model string) error {
	max := 1
	_, err := p.Chat(ctx, models.ChatRequest{
		Model: model,
		Messages: []models.ChatMessage{
			{Role: "user", Content: "ping"},
		},
		MaxTokens: &max,
	})
	return err
}
