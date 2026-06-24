package mask

import (
	"fmt"
	"regexp"
	"strings"

	"github.com/aegis-platform/aegis/agent-gate/internal/models"
)

type pattern struct {
	name    string
	re      *regexp.Regexp
	replace string
}

var credentialPatterns = []pattern{
	{name: "openai_key", re: regexp.MustCompile(`(?i)\bsk-(?:live|proj|test)-[A-Za-z0-9]{10,}\b`), replace: "[REDACTED-API_KEY]"},
	{name: "aws_key", re: regexp.MustCompile(`\bAKIA[0-9A-Z]{16}\b`), replace: "[REDACTED-AWS_KEY]"},
	{name: "password", re: regexp.MustCompile(`(?i)(password|passwd|pwd)\s*[:=]\s*\S+`), replace: "[REDACTED-PASSWORD]"},
	{name: "api_key", re: regexp.MustCompile(`(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['"]?\S+`), replace: "[REDACTED-SECRET]"},
	{name: "jwt", re: regexp.MustCompile(`\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b`), replace: "[REDACTED-JWT]"},
	{name: "private_key", re: regexp.MustCompile(`-----BEGIN (?:RSA |EC )?PRIVATE KEY-----`), replace: "[REDACTED-PRIVATE_KEY]"},
}

// EnrichArgument detects credentials and applies masking on string values.
func EnrichArgument(arg *models.ToolArgument) {
	if arg == nil {
		return
	}
	if arg.TaintLevel == "" {
		arg.TaintLevel = models.TaintTrusted
	}

	text := valueAsString(arg.Value)
	if text == "" {
		return
	}

	masked := text
	matched := false
	for _, p := range credentialPatterns {
		if p.re.MatchString(masked) {
			matched = true
			masked = p.re.ReplaceAllString(masked, p.replace)
		}
	}

	if matched {
		arg.ContainsCredentials = true
		arg.MaskedValue = masked
		if arg.TaintLevel != models.TaintTainted {
			arg.TaintLevel = models.TaintUntrusted
		}
	}
}

// SanitizeToolCall returns a copy with credentials masked in argument values.
func SanitizeToolCall(call models.ToolCallRequest) models.ToolCallRequest {
	out := call
	out.Arguments = make([]models.ToolArgument, len(call.Arguments))
	for i, arg := range call.Arguments {
		copyArg := arg
		EnrichArgument(&copyArg)
		if copyArg.MaskedValue != "" {
			copyArg.Value = copyArg.MaskedValue
		}
		out.Arguments[i] = copyArg
	}
	return out
}

func valueAsString(v any) string {
	switch t := v.(type) {
	case string:
		return t
	case fmt.Stringer:
		return t.String()
	default:
		return strings.TrimSpace(fmt.Sprint(v))
	}
}
