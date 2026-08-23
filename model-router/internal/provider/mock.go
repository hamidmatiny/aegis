package provider

import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/aegis-platform/aegis/model-router/internal/models"
)

// MockEmbeddingDims matches common OpenAI embedding width (and AEGIS infra_memory).
const MockEmbeddingDims = 1536

// Mock provides deterministic responses for dev/test without upstream API keys.
type Mock struct {
	cfg ProviderConfig
}

func NewMock(cfg ProviderConfig) (Provider, error) {
	if cfg.DefaultModel == "" {
		cfg.DefaultModel = "mock-model"
	}
	if cfg.DefaultEmbeddingModel == "" {
		cfg.DefaultEmbeddingModel = "mock-embedding"
	}
	cfg.SupportsEmbeddings = true
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

func (p *Mock) Embed(_ context.Context, req models.EmbeddingRequest) (*models.EmbeddingResponse, error) {
	if len(req.Input.Texts) == 0 {
		return nil, fmt.Errorf("input required")
	}
	model := req.Model
	if model == "" {
		model = p.cfg.DefaultEmbeddingModel
	}
	data := make([]models.EmbeddingData, len(req.Input.Texts))
	promptTokens := 0
	for i, text := range req.Input.Texts {
		data[i] = models.EmbeddingData{
			Object:    "embedding",
			Index:     i,
			Embedding: DeterministicEmbedding(text, MockEmbeddingDims),
		}
		n := len(strings.Fields(text))
		if n == 0 {
			n = 1
		}
		promptTokens += n
	}
	return &models.EmbeddingResponse{
		Object:   "list",
		Data:     data,
		Model:    model,
		Provider: p.cfg.ID,
		Usage: models.EmbeddingUsage{
			PromptTokens: promptTokens,
			TotalTokens:  promptTokens,
		},
	}, nil
}

// DeterministicEmbedding expands a SHA-256 digest of text into dims float64s in [-1, 1].
func DeterministicEmbedding(text string, dims int) []float64 {
	if dims <= 0 {
		dims = MockEmbeddingDims
	}
	out := make([]float64, dims)
	seed := sha256.Sum256([]byte(text))
	block := seed
	for i := 0; i < dims; i++ {
		if i%8 == 0 && i > 0 {
			block = sha256.Sum256(append(block[:], byte(i/8)))
		}
		u := binary.BigEndian.Uint32(block[(i%8)*4 : (i%8)*4+4])
		out[i] = (float64(u)/float64(math.MaxUint32))*2 - 1
	}
	return out
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
