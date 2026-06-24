package mask_test

import (
	"testing"

	"github.com/aegis-platform/aegis/agent-gate/internal/mask"
	"github.com/aegis-platform/aegis/agent-gate/internal/models"
)

func TestEnrichArgumentMasksAPIKey(t *testing.T) {
	arg := models.ToolArgument{
		Name:  "body",
		Value: "send api_key=sk-live-abc123xyz789012345678 to server",
	}
	mask.EnrichArgument(&arg)
	if !arg.ContainsCredentials {
		t.Fatal("expected contains_credentials")
	}
	if arg.MaskedValue == "" {
		t.Fatal("expected masked_value")
	}
}

func TestSanitizeToolCallPreservesBenign(t *testing.T) {
	call := models.ToolCallRequest{
		ToolName: "search",
		Arguments: []models.ToolArgument{
			{Name: "query", Value: "weather in Paris"},
		},
	}
	out := mask.SanitizeToolCall(call)
	if out.Arguments[0].ContainsCredentials {
		t.Fatal("benign query should not flag credentials")
	}
}
