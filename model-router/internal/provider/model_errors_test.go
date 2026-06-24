package provider

import (
	"strings"
	"testing"
)

func TestClassifyGrokModelNotFound(t *testing.T) {
	body := `{"code":"invalid-argument","error":"Model not found"}`
	err := classifyUpstreamError("grok", "grok-2-latest", 400, body)
	modelErr, ok := AsModelRetiredError(err)
	if !ok {
		t.Fatalf("expected ModelRetiredError, got %T: %v", err, err)
	}
	if modelErr.RejectedModel != "grok-2-latest" {
		t.Fatalf("unexpected model: %s", modelErr.RejectedModel)
	}
}

func TestClassifyOpenAIModelNotFound(t *testing.T) {
	body := `{"error":{"code":"model_not_found","message":"The model gpt-foo does not exist"}}`
	err := classifyUpstreamError("openai", "gpt-foo", 404, body)
	if _, ok := AsModelRetiredError(err); !ok {
		t.Fatalf("expected ModelRetiredError, got %v", err)
	}
}

func TestClassifyAnthropicModelNotFound(t *testing.T) {
	body := `{"type":"error","error":{"type":"not_found_error","message":"model: claude-old"}}`
	err := classifyUpstreamError("anthropic", "claude-old", 404, body)
	if _, ok := AsModelRetiredError(err); !ok {
		t.Fatalf("expected ModelRetiredError, got %v", err)
	}
}

func TestTransientErrorNotModelRetired(t *testing.T) {
	body := `{"error":"internal server error"}`
	err := classifyUpstreamError("openai", "gpt-4o-mini", 500, body)
	if IsModelRetiredError(err) {
		t.Fatal("500 should not be classified as model retired")
	}
	if _, ok := err.(*UpstreamError); !ok {
		t.Fatalf("expected UpstreamError, got %T", err)
	}
}

func TestModelRetiredGuidanceMentionsProvidersYAML(t *testing.T) {
	err := &ModelRetiredError{Provider: "grok", RejectedModel: "grok-2-latest"}
	g := err.Guidance()
	for _, part := range []string{"grok-2-latest", "grok", "providers.yaml"} {
		if !strings.Contains(g, part) {
			t.Fatalf("guidance missing %q: %s", part, g)
		}
	}
}
