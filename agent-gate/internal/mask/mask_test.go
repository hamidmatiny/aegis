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

// TestEnrichArgumentEscalatesTaintLevelToTainted is the Stage E.1
// regression guard: a server-detected credential must escalate
// TaintLevel all the way to TAINTED, not just UNTRUSTED. The only policy
// rule that used to guard against credential exfiltration required
// exactly TAINTED, so stopping at UNTRUSTED here silently defeated it
// for any caller that didn't also explicitly declare TAINTED itself.
func TestEnrichArgumentEscalatesTaintLevelToTainted(t *testing.T) {
	arg := models.ToolArgument{
		Name:  "body",
		Value: "here is the key: sk-live-abc123xyz789012345678",
	}
	mask.EnrichArgument(&arg)
	if !arg.ContainsCredentials {
		t.Fatal("expected contains_credentials")
	}
	if arg.TaintLevel != models.TaintTainted {
		t.Fatalf("expected taint_level TAINTED, got %q", arg.TaintLevel)
	}
}

// TestEnrichArgumentDoesNotFlagCleanValue is the false-positive guard:
// a value with no credential-shaped content must not be flagged, and
// must default to TRUSTED when the caller didn't set a taint_level.
func TestEnrichArgumentDoesNotFlagCleanValue(t *testing.T) {
	arg := models.ToolArgument{
		Name:  "query",
		Value: "weather in Paris",
	}
	mask.EnrichArgument(&arg)
	if arg.ContainsCredentials {
		t.Fatal("clean value should not flag credentials")
	}
	if arg.TaintLevel != models.TaintTrusted {
		t.Fatalf("expected default taint_level TRUSTED, got %q", arg.TaintLevel)
	}
}
