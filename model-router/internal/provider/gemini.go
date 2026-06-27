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

// Gemini implements the Google Generative Language API.
type Gemini struct {
	cfg    ProviderConfig
	client *http.Client
}

func NewGemini(cfg ProviderConfig) (Provider, error) {
	base := strings.TrimRight(cfg.BaseURL, "/")
	if base == "" {
		base = "https://generativelanguage.googleapis.com/v1beta"
	}
	cfg.BaseURL = base
	return &Gemini{cfg: cfg, client: &http.Client{Timeout: 120 * time.Second}}, nil
}

func (p *Gemini) ID() string { return p.cfg.ID }

func (p *Gemini) Ping(ctx context.Context) error {
	if ResolveAPIKey(p.cfg) == "" {
		return fmt.Errorf("gemini: missing API key")
	}
	return nil
}

func (p *Gemini) geminiKey() string {
	return ResolveAPIKey(p.cfg)
}

func (p *Gemini) Chat(ctx context.Context, req models.ChatRequest) (*models.ChatResponse, error) {
	model := req.Model
	if model == "" {
		model = p.cfg.DefaultModel
	}
	if model == "" {
		model = "gemini-1.5-flash"
	}
	url := fmt.Sprintf("%s/models/%s:generateContent?key=%s", p.cfg.BaseURL, model, p.geminiKey())
	body, err := json.Marshal(p.buildPayload(req))
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := p.client.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, classifyUpstreamError(p.cfg.ID, model, p.cfg.APIKeyEnv, resp.StatusCode, string(raw))
	}

	var parsed geminiResponse
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, err
	}
	content := ""
	for _, cand := range parsed.Candidates {
		for _, part := range cand.Content.Parts {
			content += part.Text
		}
	}
	return &models.ChatResponse{
		ID:       "gemini-" + model,
		Provider: p.cfg.ID,
		Model:    model,
		Content:  content,
		Usage: models.Usage{
			PromptTokens:     parsed.UsageMetadata.PromptTokenCount,
			CompletionTokens: parsed.UsageMetadata.CandidatesTokenCount,
			TotalTokens:      parsed.UsageMetadata.TotalTokenCount,
		},
		CreatedAt: time.Now().UTC(),
	}, nil
}

func (p *Gemini) ChatStream(ctx context.Context, req models.ChatRequest) (<-chan models.StreamChunk, error) {
	model := req.Model
	if model == "" {
		model = p.cfg.DefaultModel
	}
	if model == "" {
		model = "gemini-1.5-flash"
	}
	url := fmt.Sprintf("%s/models/%s:streamGenerateContent?alt=sse&key=%s", p.cfg.BaseURL, model, p.geminiKey())
	body, err := json.Marshal(p.buildPayload(req))
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := p.client.Do(httpReq)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		raw, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		return nil, classifyUpstreamError(p.cfg.ID, model, p.cfg.APIKeyEnv, resp.StatusCode, string(raw))
	}

	out := make(chan models.StreamChunk, 16)
	go func() {
		defer close(out)
		defer resp.Body.Close()
		dec := json.NewDecoder(resp.Body)
		for {
			var parsed geminiResponse
			if err := dec.Decode(&parsed); err != nil {
				if err == io.EOF {
					out <- models.StreamChunk{Done: true, Provider: p.cfg.ID, Model: model}
				}
				return
			}
			for _, cand := range parsed.Candidates {
				for _, part := range cand.Content.Parts {
					if part.Text != "" {
						out <- models.StreamChunk{
							Provider: p.cfg.ID,
							Model:    model,
							Delta:    part.Text,
						}
					}
				}
			}
		}
	}()
	return out, nil
}

func (p *Gemini) buildPayload(req models.ChatRequest) map[string]any {
	var contents []map[string]any
	for _, m := range req.Messages {
		role := "user"
		if m.Role == "assistant" {
			role = "model"
		}
		if m.Role == "system" {
			role = "user"
		}
		contents = append(contents, map[string]any{
			"role":  role,
			"parts": []map[string]string{{"text": m.Content}},
		})
	}
	payload := map[string]any{"contents": contents}
	genConfig := map[string]any{}
	if req.Temperature != nil {
		genConfig["temperature"] = *req.Temperature
	}
	if req.MaxTokens != nil {
		genConfig["maxOutputTokens"] = *req.MaxTokens
	}
	if len(genConfig) > 0 {
		payload["generationConfig"] = genConfig
	}
	return payload
}

// CheckModel sends a minimal request to verify the model ID is accepted.
func (p *Gemini) CheckModel(ctx context.Context, model string) error {
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

type geminiResponse struct {
	Candidates []struct {
		Content struct {
			Parts []struct {
				Text string `json:"text"`
			} `json:"parts"`
		} `json:"content"`
	} `json:"candidates"`
	UsageMetadata struct {
		PromptTokenCount     int `json:"promptTokenCount"`
		CandidatesTokenCount int `json:"candidatesTokenCount"`
		TotalTokenCount      int `json:"totalTokenCount"`
	} `json:"usageMetadata"`
}
