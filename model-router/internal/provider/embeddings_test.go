package provider_test

import (
	"context"
	"math"
	"testing"

	"github.com/aegis-platform/aegis/model-router/internal/models"
	"github.com/aegis-platform/aegis/model-router/internal/provider"
)

func TestMockEmbedDeterministic(t *testing.T) {
	p, err := provider.NewMock(provider.ProviderConfig{ID: "mock"})
	if err != nil {
		t.Fatal(err)
	}
	ep, ok := p.(provider.EmbeddingProvider)
	if !ok {
		t.Fatal("mock must implement EmbeddingProvider")
	}
	a, err := ep.Embed(context.Background(), models.EmbeddingRequest{
		Model: "mock-embedding",
		Input: models.EmbeddingInput{Texts: []string{"hello"}},
	})
	if err != nil {
		t.Fatal(err)
	}
	b, err := ep.Embed(context.Background(), models.EmbeddingRequest{
		Input: models.EmbeddingInput{Texts: []string{"hello"}},
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(a.Data) != 1 || len(a.Data[0].Embedding) != provider.MockEmbeddingDims {
		t.Fatalf("expected %d dims, got %d", provider.MockEmbeddingDims, len(a.Data[0].Embedding))
	}
	for i := range a.Data[0].Embedding {
		if a.Data[0].Embedding[i] != b.Data[0].Embedding[i] {
			t.Fatalf("embedding not deterministic at index %d", i)
		}
		if math.IsNaN(a.Data[0].Embedding[i]) {
			t.Fatal("NaN in embedding")
		}
	}
	other, err := ep.Embed(context.Background(), models.EmbeddingRequest{
		Input: models.EmbeddingInput{Texts: []string{"different"}},
	})
	if err != nil {
		t.Fatal(err)
	}
	same := true
	for i := range a.Data[0].Embedding {
		if a.Data[0].Embedding[i] != other.Data[0].Embedding[i] {
			same = false
			break
		}
	}
	if same {
		t.Fatal("different inputs should not produce identical embeddings")
	}
}

func TestOpenAICompatEmbedRejectedWhenDisabled(t *testing.T) {
	p, err := provider.NewOpenAICompat(provider.ProviderConfig{
		ID:                 "grok",
		BaseURL:            "https://api.x.ai/v1",
		SupportsEmbeddings: false,
	})
	if err != nil {
		t.Fatal(err)
	}
	ep, ok := p.(provider.EmbeddingProvider)
	if !ok {
		t.Fatal("openai compat should expose Embed")
	}
	_, err = ep.Embed(context.Background(), models.EmbeddingRequest{
		Input: models.EmbeddingInput{Texts: []string{"test"}},
	})
	if !provider.IsEmbeddingNotSupportedError(err) {
		t.Fatalf("expected EmbeddingNotSupportedError, got %v", err)
	}
}
