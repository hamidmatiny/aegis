package provider

import (
	"bufio"
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

// OpenAICompat implements OpenAI-compatible APIs (OpenAI, Ollama, vLLM, Grok/xAI).
type OpenAICompat struct {
	cfg    ProviderConfig
	client *http.Client
}

func NewOpenAICompat(cfg ProviderConfig) (Provider, error) {
	base := strings.TrimRight(cfg.BaseURL, "/")
	if base == "" {
		switch cfg.ID {
		case "ollama":
			base = "http://localhost:11434"
		case "vllm":
			base = "http://localhost:8000"
		case "grok":
			base = "https://api.x.ai/v1"
		default:
			base = "https://api.openai.com/v1"
		}
	}
	cfg.BaseURL = base
	return &OpenAICompat{
		cfg:    cfg,
		client: &http.Client{Timeout: 120 * time.Second},
	}, nil
}

func (p *OpenAICompat) ID() string { return p.cfg.ID }

func (p *OpenAICompat) Ping(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, p.cfg.BaseURL+"/models", nil)
	if err != nil {
		return err
	}
	p.applyHeaders(req)
	resp, err := p.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("ping status %d", resp.StatusCode)
	}
	return nil
}

func (p *OpenAICompat) Chat(ctx context.Context, req models.ChatRequest) (*models.ChatResponse, error) {
	body, err := json.Marshal(p.buildPayload(req, false))
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, p.cfg.BaseURL+"/chat/completions", bytes.NewReader(body))
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
		model := modelFromRequest(req.Model, p.cfg.DefaultModel)
		return nil, classifyUpstreamError(p.cfg.ID, model, resp.StatusCode, string(raw))
	}

	var parsed openAIResponse
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, err
	}
	content := ""
	finish := ""
	if len(parsed.Choices) > 0 {
		content = parsed.Choices[0].Message.Content
		finish = parsed.Choices[0].FinishReason
	}
	return &models.ChatResponse{
		ID:           parsed.ID,
		Provider:     p.cfg.ID,
		Model:        parsed.Model,
		Content:      content,
		FinishReason: finish,
		Usage: models.Usage{
			PromptTokens:     parsed.Usage.PromptTokens,
			CompletionTokens: parsed.Usage.CompletionTokens,
			TotalTokens:      parsed.Usage.TotalTokens,
		},
		CreatedAt: time.Now().UTC(),
	}, nil
}

func (p *OpenAICompat) ChatStream(ctx context.Context, req models.ChatRequest) (<-chan models.StreamChunk, error) {
	body, err := json.Marshal(p.buildPayload(req, true))
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, p.cfg.BaseURL+"/chat/completions", bytes.NewReader(body))
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
		model := modelFromRequest(req.Model, p.cfg.DefaultModel)
		return nil, classifyUpstreamError(p.cfg.ID, model, resp.StatusCode, string(raw))
	}

	out := make(chan models.StreamChunk, 16)
	go func() {
		defer close(out)
		defer resp.Body.Close()
		scanner := bufio.NewScanner(resp.Body)
		for scanner.Scan() {
			line := scanner.Text()
			if !strings.HasPrefix(line, "data: ") {
				continue
			}
			data := strings.TrimPrefix(line, "data: ")
			if data == "[DONE]" {
				out <- models.StreamChunk{Done: true, Provider: p.cfg.ID, Model: req.Model}
				return
			}
			var chunk openAIStreamChunk
			if err := json.Unmarshal([]byte(data), &chunk); err != nil {
				continue
			}
			delta := ""
			finish := ""
			if len(chunk.Choices) > 0 {
				delta = chunk.Choices[0].Delta.Content
				finish = chunk.Choices[0].FinishReason
			}
			out <- models.StreamChunk{
				ID:           chunk.ID,
				Provider:     p.cfg.ID,
				Model:        chunk.Model,
				Delta:        delta,
				FinishReason: finish,
			}
		}
	}()
	return out, nil
}

func (p *OpenAICompat) buildPayload(req models.ChatRequest, stream bool) map[string]any {
	model := req.Model
	if model == "" {
		model = p.cfg.DefaultModel
	}
	msgs := make([]map[string]string, len(req.Messages))
	for i, m := range req.Messages {
		msgs[i] = map[string]string{"role": m.Role, "content": m.Content}
	}
	payload := map[string]any{
		"model":    model,
		"messages": msgs,
		"stream":   stream,
	}
	if req.Temperature != nil {
		payload["temperature"] = *req.Temperature
	}
	if req.MaxTokens != nil {
		payload["max_tokens"] = *req.MaxTokens
	}
	return payload
}

func (p *OpenAICompat) applyHeaders(req *http.Request) {
	if p.cfg.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+p.cfg.APIKey)
	}
	for k, v := range p.cfg.ExtraHeaders {
		req.Header.Set(k, v)
	}
}

type openAIResponse struct {
	ID      string `json:"id"`
	Model   string `json:"model"`
	Choices []struct {
		Message      struct{ Content string } `json:"message"`
		FinishReason string                   `json:"finish_reason"`
	} `json:"choices"`
	Usage struct {
		PromptTokens     int `json:"prompt_tokens"`
		CompletionTokens int `json:"completion_tokens"`
		TotalTokens      int `json:"total_tokens"`
	} `json:"usage"`
}

type openAIStreamChunk struct {
	ID      string `json:"id"`
	Model   string `json:"model"`
	Choices []struct {
		Delta        struct{ Content string } `json:"delta"`
		FinishReason string                   `json:"finish_reason"`
	} `json:"choices"`
}

// UpstreamError wraps a non-2xx upstream response.
type UpstreamError struct {
	Provider string
	Status   int
	Body     string
}

func (e *UpstreamError) Error() string {
	return fmt.Sprintf("%s upstream error %d: %s", e.Provider, e.Status, e.Body)
}

func retryableStatus(code int) bool {
	return code == 429 || code >= 500
}

func (e *UpstreamError) Retryable() bool {
	return retryableStatus(e.Status)
}

// CheckModel sends a minimal completion to verify the model ID is accepted.
func (p *OpenAICompat) CheckModel(ctx context.Context, model string) error {
	_, err := p.Chat(ctx, models.ChatRequest{
		Model: model,
		Messages: []models.ChatMessage{
			{Role: "user", Content: "ping"},
		},
		MaxTokens: intPtr(1),
	})
	return err
}

func intPtr(v int) *int { return &v }
