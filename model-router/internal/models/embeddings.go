package models

import (
	"encoding/json"
	"fmt"
)

// EmbeddingRequest is an OpenAI-compatible embeddings request.
type EmbeddingRequest struct {
	Provider string         `json:"provider,omitempty"`
	Model    string         `json:"model"`
	Input    EmbeddingInput `json:"input"`
}

// EmbeddingInput accepts a single string or a list of strings (OpenAI shape).
type EmbeddingInput struct {
	Texts []string
}

func (e *EmbeddingInput) UnmarshalJSON(data []byte) error {
	var single string
	if err := json.Unmarshal(data, &single); err == nil {
		e.Texts = []string{single}
		return nil
	}
	var many []string
	if err := json.Unmarshal(data, &many); err == nil {
		if len(many) == 0 {
			return fmt.Errorf("input must be a non-empty string or array of strings")
		}
		e.Texts = many
		return nil
	}
	return fmt.Errorf("input must be a string or array of strings")
}

func (e EmbeddingInput) MarshalJSON() ([]byte, error) {
	if len(e.Texts) == 1 {
		return json.Marshal(e.Texts[0])
	}
	return json.Marshal(e.Texts)
}

// EmbeddingData is one vector in an embeddings response.
type EmbeddingData struct {
	Object    string    `json:"object"`
	Embedding []float64 `json:"embedding"`
	Index     int       `json:"index"`
}

// EmbeddingUsage reports token usage when available.
type EmbeddingUsage struct {
	PromptTokens int `json:"prompt_tokens"`
	TotalTokens  int `json:"total_tokens"`
}

// EmbeddingResponse is the unified embeddings response (OpenAI-compatible).
type EmbeddingResponse struct {
	Object   string          `json:"object"`
	Data     []EmbeddingData `json:"data"`
	Model    string          `json:"model"`
	Provider string          `json:"provider,omitempty"`
	Usage    EmbeddingUsage  `json:"usage"`
}
