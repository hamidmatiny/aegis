package engine

import (
	"fmt"

	"github.com/google/cel-go/cel"
	"github.com/google/cel-go/common/types"
	"github.com/google/cel-go/common/types/ref"

	"github.com/aegis-platform/aegis/policy-engine/internal/models"
)

func newInputEnv() (*cel.Env, error) {
	return cel.NewEnv(
		cel.Variable("input_verdict", cel.DynType),
		cel.Variable("tenant_id", cel.StringType),
	)
}

func newOutputEnv() (*cel.Env, error) {
	return cel.NewEnv(
		cel.Variable("output_verdict", cel.DynType),
		cel.Variable("tenant_id", cel.StringType),
	)
}

func newToolEnv() (*cel.Env, error) {
	return cel.NewEnv(
		cel.Variable("tool_call", cel.DynType),
		cel.Variable("tenant_id", cel.StringType),
	)
}

func compileProgram(env *cel.Env, expression string) (cel.Program, error) {
	ast, issues := env.Compile(expression)
	if issues != nil && issues.Err() != nil {
		return nil, fmt.Errorf("compile CEL %q: %w", expression, issues.Err())
	}
	prog, err := env.Program(ast)
	if err != nil {
		return nil, fmt.Errorf("program CEL %q: %w", expression, err)
	}
	return prog, nil
}

func evalBool(prog cel.Program, activation map[string]any) (bool, string, error) {
	out, _, err := prog.Eval(activation)
	if err != nil {
		return false, "", err
	}
	if b, ok := out.Value().(bool); ok {
		return b, "", nil
	}
	if b, ok := out.(types.Bool); ok {
		return bool(b), "", nil
	}
	return false, fmt.Sprintf("CEL expression returned %v (%T), expected bool", out.Value(), out.Value()), nil
}

func inputActivation(tenantID string, verdict models.InputVerdict) map[string]any {
	return map[string]any{
		"tenant_id": tenantID,
		"input_verdict": map[string]any{
			"action":              verdict.Action,
			"fused_score":         verdict.FusedScore,
			"detector_scores":     detectorScoresToMaps(verdict.DetectorScores),
			"transformed_content": derefString(verdict.TransformedContent),
			"escalation_reason":   derefString(verdict.EscalationReason),
			"total_latency_ms":    verdict.TotalLatencyMS,
			"request_id":          derefString(verdict.RequestID),
		},
	}
}

func outputActivation(tenantID string, verdict models.OutputVerdict) map[string]any {
	return map[string]any{
		"tenant_id": tenantID,
		"output_verdict": map[string]any{
			"action":           verdict.Action,
			"fused_score":      verdict.FusedScore,
			"detector_scores":  detectorScoresToMaps(verdict.DetectorScores),
			"redacted_content": derefString(verdict.RedactedContent),
		},
	}
}

func toolActivation(tenantID string, call models.ToolCallRequest) map[string]any {
	args := make([]map[string]any, len(call.Arguments))
	for i, a := range call.Arguments {
		args[i] = map[string]any{
			"name":                 a.Name,
			"taint_level":          a.TaintLevel,
			"contains_credentials": a.ContainsCredentials,
		}
	}
	return map[string]any{
		"tenant_id": tenantID,
		"tool_call": map[string]any{
			"tool_name":  call.ToolName,
			"risk_level": call.RiskLevel,
			"arguments":  args,
		},
	}
}

func detectorScoresToMaps(scores []models.DetectorScore) []map[string]any {
	out := make([]map[string]any, len(scores))
	for i, s := range scores {
		out[i] = map[string]any{
			"detector_id":      s.DetectorID,
			"detector_version": s.DetectorVersion,
			"score":            s.Score,
			"reasoning":        s.Reasoning,
			"latency_ms":       s.LatencyMS,
			"metadata":         s.Metadata,
		}
	}
	return out
}

func derefString(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

// unused but keeps cel types linked for future extensions
var _ ref.Val = types.Bool(true)
