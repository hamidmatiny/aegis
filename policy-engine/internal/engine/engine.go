package engine

import (
	"fmt"
	"time"

	"github.com/google/cel-go/cel"

	"github.com/aegis-platform/aegis/policy-engine/internal/models"
)

// actionSeverity ranks actions for multi-rule fusion (higher = more restrictive).
var actionSeverity = map[models.Action]int{
	models.ActionAllow:           0,
	models.ActionTransform:       1,
	models.ActionEscalateToJudge: 2,
	models.ActionBlock:           3,
}

// Engine evaluates CEL policy rules against defense verdicts.
type Engine struct{}

func New() *Engine {
	return &Engine{}
}

func (e *Engine) EvaluateInput(
	pack models.PolicyPack,
	tenantID string,
	verdict models.InputVerdict,
	mode models.EvaluationMode,
) (models.PolicyDecision, error) {
	env, err := newInputEnv()
	if err != nil {
		return models.PolicyDecision{}, err
	}
	return e.evaluate(
		pack,
		tenantID,
		mode,
		pack.InputRules,
		env,
		inputActivation(tenantID, verdict),
	)
}

func (e *Engine) EvaluateOutput(
	pack models.PolicyPack,
	tenantID string,
	verdict models.OutputVerdict,
	mode models.EvaluationMode,
) (models.PolicyDecision, error) {
	env, err := newOutputEnv()
	if err != nil {
		return models.PolicyDecision{}, err
	}
	return e.evaluate(
		pack,
		tenantID,
		mode,
		pack.OutputRules,
		env,
		outputActivation(tenantID, verdict),
	)
}

func (e *Engine) EvaluateTool(
	pack models.PolicyPack,
	tenantID string,
	call models.ToolCallRequest,
	mode models.EvaluationMode,
) (models.PolicyDecision, error) {
	env, err := newToolEnv()
	if err != nil {
		return models.PolicyDecision{}, err
	}
	return e.evaluate(
		pack,
		tenantID,
		mode,
		pack.ToolRules,
		env,
		toolActivation(tenantID, call),
	)
}

func (e *Engine) evaluate(
	pack models.PolicyPack,
	tenantID string,
	mode models.EvaluationMode,
	rules []models.PolicyRule,
	env *cel.Env,
	activation map[string]any,
) (models.PolicyDecision, error) {
	start := time.Now()
	if mode == "" {
		mode = models.ModeEnforce
	}
	if pack.Settings.DefaultAction == "" {
		pack.Settings.DefaultAction = models.ActionAllow
	}

	computed := pack.Settings.DefaultAction
	var transformSpec string
	var blockReason string
	matches := make([]models.PolicyRuleMatch, 0, len(rules))

	for _, rule := range rules {
		match := models.PolicyRuleMatch{
			RuleID:        rule.ID,
			RuleName:      rule.Name,
			CELExpression: rule.CEL,
			Matched:       false,
		}
		if !rule.Enabled {
			match.MatchReason = "rule disabled"
			matches = append(matches, match)
			continue
		}

		prog, err := compileProgram(env, rule.CEL)
		if err != nil {
			return models.PolicyDecision{}, fmt.Errorf("rule %q: %w", rule.ID, err)
		}
		ok, reason, err := evalBool(prog, activation)
		if err != nil {
			return models.PolicyDecision{}, fmt.Errorf("rule %q eval: %w", rule.ID, err)
		}
		if reason != "" {
			match.MatchReason = reason
		}
		match.Matched = ok
		matches = append(matches, match)

		if ok && actionSeverity[rule.Action] >= actionSeverity[computed] {
			computed = rule.Action
			if rule.Action == models.ActionBlock {
				blockReason = fmt.Sprintf("rule %q (%s) matched", rule.ID, rule.Name)
			}
			if rule.Action == models.ActionTransform && rule.TransformSpec != "" {
				transformSpec = rule.TransformSpec
			}
		}
	}

	decision := models.PolicyDecision{
		PolicyPackID:        pack.ID,
		PolicyPackVersion:   pack.Version,
		MatchedRules:        matches,
		BlockReason:         blockReason,
		TransformSpec:       transformSpec,
		Mode:                mode,
		TenantID:            tenantID,
		EvaluatedAt:         time.Now().UTC(),
		EvaluationLatencyMS: time.Since(start).Milliseconds(),
	}

	decision.ShadowAction = computed
	decision.Action = computed

	if mode == models.ModeShadow || mode == models.ModeDryRun {
		decision.Action = pack.Settings.DefaultAction
	}

	return decision, nil
}
