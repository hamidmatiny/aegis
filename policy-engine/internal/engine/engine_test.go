package engine_test

import (
	"testing"

	"github.com/aegis-platform/aegis/policy-engine/internal/engine"
	"github.com/aegis-platform/aegis/policy-engine/internal/models"
)

func sampleVerdict(score float64, action string) models.InputVerdict {
	content := "wrapped"
	return models.InputVerdict{
		Action:     action,
		FusedScore: score,
		DetectorScores: []models.DetectorScore{
			{DetectorID: "heuristic", Score: score, Reasoning: "test"},
		},
		TransformedContent: &content,
	}
}

func TestEvaluateInputBlockHighScore(t *testing.T) {
	eng := engine.New()
	pack := models.PolicyPack{
		ID:      "default",
		Version: "0.2.0",
		InputRules: []models.PolicyRule{
			{
				ID: "block-high", Name: "Block high", CEL: "input_verdict.fused_score >= 0.85",
				Action: models.ActionBlock, Enabled: true,
			},
		},
		Settings: models.PolicySettings{DefaultAction: models.ActionAllow},
	}

	decision, err := eng.EvaluateInput(pack, "default", sampleVerdict(0.92, "BLOCK"), models.ModeEnforce)
	if err != nil {
		t.Fatalf("EvaluateInput: %v", err)
	}
	if decision.Action != models.ActionBlock {
		t.Fatalf("expected block, got %s", decision.Action)
	}
}

func TestEvaluateInputEscalateAmbiguous(t *testing.T) {
	eng := engine.New()
	pack := models.PolicyPack{
		ID:      "default",
		Version: "0.2.0",
		InputRules: []models.PolicyRule{
			{
				ID: "escalate", Name: "Escalate", CEL: "input_verdict.fused_score >= 0.55 && input_verdict.fused_score < 0.85",
				Action: models.ActionEscalateToJudge, Enabled: true,
			},
		},
		Settings: models.PolicySettings{DefaultAction: models.ActionAllow},
	}

	decision, err := eng.EvaluateInput(pack, "default", sampleVerdict(0.65, "ESCALATE"), models.ModeEnforce)
	if err != nil {
		t.Fatalf("EvaluateInput: %v", err)
	}
	if decision.Action != models.ActionEscalateToJudge {
		t.Fatalf("expected escalate, got %s", decision.Action)
	}
}

func TestEvaluateInputAllowLowScore(t *testing.T) {
	eng := engine.New()
	pack := models.PolicyPack{
		ID:      "default",
		Version: "0.2.0",
		InputRules: []models.PolicyRule{
			{
				ID: "block-high", Name: "Block high", CEL: "input_verdict.fused_score >= 0.85",
				Action: models.ActionBlock, Enabled: true,
			},
		},
		Settings: models.PolicySettings{DefaultAction: models.ActionAllow},
	}

	decision, err := eng.EvaluateInput(pack, "default", sampleVerdict(0.12, "ALLOW"), models.ModeEnforce)
	if err != nil {
		t.Fatalf("EvaluateInput: %v", err)
	}
	if decision.Action != models.ActionAllow {
		t.Fatalf("expected allow, got %s", decision.Action)
	}
}

func TestShadowModeDoesNotEnforceBlock(t *testing.T) {
	eng := engine.New()
	pack := models.PolicyPack{
		ID:      "default",
		Version: "0.2.0",
		InputRules: []models.PolicyRule{
			{
				ID: "block-high", Name: "Block high", CEL: "input_verdict.fused_score >= 0.85",
				Action: models.ActionBlock, Enabled: true,
			},
		},
		Settings: models.PolicySettings{DefaultAction: models.ActionAllow},
	}

	decision, err := eng.EvaluateInput(pack, "default", sampleVerdict(0.95, "BLOCK"), models.ModeShadow)
	if err != nil {
		t.Fatalf("EvaluateInput: %v", err)
	}
	if decision.Action != models.ActionAllow {
		t.Fatalf("shadow enforce action should be allow, got %s", decision.Action)
	}
	if decision.ShadowAction != models.ActionBlock {
		t.Fatalf("shadow_action should be block, got %s", decision.ShadowAction)
	}
}

func TestDetectorScoreCELExists(t *testing.T) {
	eng := engine.New()
	pack := models.PolicyPack{
		ID:      "default",
		Version: "0.2.0",
		InputRules: []models.PolicyRule{
			{
				ID: "heuristic-block", Name: "Heuristic block",
				CEL:    "input_verdict.detector_scores.exists(d, d.detector_id == 'heuristic' && d.score >= 0.80)",
				Action: models.ActionBlock, Enabled: true,
			},
		},
		Settings: models.PolicySettings{DefaultAction: models.ActionAllow},
	}

	decision, err := eng.EvaluateInput(pack, "default", sampleVerdict(0.40, "ALLOW"), models.ModeEnforce)
	if err != nil {
		t.Fatalf("EvaluateInput: %v", err)
	}
	// sampleVerdict sets heuristic score == fused score (0.40) — should not block
	if decision.Action != models.ActionAllow {
		t.Fatalf("expected allow for score 0.40, got %s", decision.Action)
	}

	decision, err = eng.EvaluateInput(pack, "default", sampleVerdict(0.90, "BLOCK"), models.ModeEnforce)
	if err != nil {
		t.Fatalf("EvaluateInput: %v", err)
	}
	if decision.Action != models.ActionBlock {
		t.Fatalf("expected block for heuristic 0.90, got %s", decision.Action)
	}
}

func sampleOutputVerdict(fusedScore, piiScore float64, action string) models.OutputVerdict {
	return models.OutputVerdict{
		Action:     action,
		FusedScore: fusedScore,
		DetectorScores: []models.DetectorScore{
			{DetectorID: "pii", Score: piiScore, Reasoning: "test"},
			{DetectorID: "toxicity", Score: 0.0, Reasoning: "test"},
			{DetectorID: "backtranslation", Score: 0.0, Reasoning: "test"},
		},
	}
}

// TestEvaluateOutputBlockCriticalPII covers Phase 5.3 (N23): a single
// highly-confident pii/secret detection must block even when the blended
// fused_score stays under block-high-output-score's 0.80 gate. pii is only
// one of three weighted detectors in output-defense's fusion.py
// (_FUSION_WEIGHTS: toxicity 0.35, pii 0.35, backtranslation 0.30), so a
// live credential leak that scores 0.90 on pii alone but 0.0 on the other
// two only produces fused_score=0.315 -- well under 0.80. Without this
// rule, that leak would sail through. Mirrors the input-side
// block-heuristic-critical rule and TestDetectorScoreCELExists above.
func TestEvaluateOutputBlockCriticalPII(t *testing.T) {
	eng := engine.New()
	pack := models.PolicyPack{
		ID:      "default",
		Version: "0.2.0",
		OutputRules: []models.PolicyRule{
			{
				ID: "block-high-output-score", Name: "Block high output score",
				CEL: "output_verdict.fused_score >= 0.80", Action: models.ActionBlock, Enabled: true,
			},
			{
				ID: "block-critical-pii-leak", Name: "Block critical PII leak",
				CEL:    "output_verdict.detector_scores.exists(d, d.detector_id == 'pii' && d.score >= 0.85)",
				Action: models.ActionBlock, Enabled: true,
			},
		},
		Settings: models.PolicySettings{DefaultAction: models.ActionAllow},
	}

	// No PII, low fused score -> allow.
	decision, err := eng.EvaluateOutput(pack, "default", sampleOutputVerdict(0.05, 0.05, "ALLOW"), models.ModeEnforce)
	if err != nil {
		t.Fatalf("EvaluateOutput: %v", err)
	}
	if decision.Action != models.ActionAllow {
		t.Fatalf("expected allow for pii 0.05, got %s", decision.Action)
	}

	// pii=0.90 (confident credential/PII leak), fused_score=0.315 -- below
	// block-high-output-score's 0.80 threshold. block-critical-pii-leak
	// must be the rule that fires.
	decision, err = eng.EvaluateOutput(pack, "default", sampleOutputVerdict(0.315, 0.90, "ALLOW"), models.ModeEnforce)
	if err != nil {
		t.Fatalf("EvaluateOutput: %v", err)
	}
	if decision.Action != models.ActionBlock {
		t.Fatalf("expected block for pii 0.90 despite fused_score 0.315 (below block-high-output-score), got %s", decision.Action)
	}
	found := false
	for _, m := range decision.MatchedRules {
		if m.RuleID == "block-critical-pii-leak" && m.Matched {
			found = true
		}
	}
	if !found {
		t.Fatal("expected block-critical-pii-leak to be the matched rule, not just block-high-output-score")
	}
}

func TestEvaluateToolIrreversible(t *testing.T) {
	eng := engine.New()
	pack := models.PolicyPack{
		ID:      "default",
		Version: "0.2.0",
		ToolRules: []models.PolicyRule{
			{
				ID: "irreversible", Name: "Irreversible",
				CEL: "tool_call.risk_level == 'IRREVERSIBLE'", Action: models.ActionEscalateToJudge, Enabled: true,
			},
		},
		Settings: models.PolicySettings{DefaultAction: models.ActionAllow},
	}

	call := models.ToolCallRequest{ToolName: "delete_file", RiskLevel: "IRREVERSIBLE"}
	decision, err := eng.EvaluateTool(pack, "default", call, models.ModeEnforce)
	if err != nil {
		t.Fatalf("EvaluateTool: %v", err)
	}
	if decision.Action != models.ActionEscalateToJudge {
		t.Fatalf("expected escalate, got %s", decision.Action)
	}
}

// TestEvaluateToolCatalogOverridesUnderstatedRisk guards against a caller
// (or an LLM-influenced tool-call assembler) claiming a lower risk_level
// than the operator registered for a known-dangerous tool. Without the
// catalog override, this exact call would evaluate as ALLOW instead of
// escalating for human approval.
func TestEvaluateToolCatalogOverridesUnderstatedRisk(t *testing.T) {
	eng := engine.New()
	pack := models.PolicyPack{
		ID:      "default",
		Version: "0.2.0",
		ToolRules: []models.PolicyRule{
			{
				ID: "irreversible", Name: "Irreversible",
				CEL: "tool_call.risk_level == 'IRREVERSIBLE'", Action: models.ActionEscalateToJudge, Enabled: true,
			},
		},
		ToolCatalog: []models.ToolCatalogEntry{
			{ToolName: "delete_database", RiskLevel: "IRREVERSIBLE"},
		},
		Settings: models.PolicySettings{DefaultAction: models.ActionAllow},
	}

	call := models.ToolCallRequest{ToolName: "delete_database", RiskLevel: "LOW"}
	decision, err := eng.EvaluateTool(pack, "default", call, models.ModeEnforce)
	if err != nil {
		t.Fatalf("EvaluateTool: %v", err)
	}
	if decision.Action != models.ActionEscalateToJudge {
		t.Fatalf("expected escalate despite understated risk_level, got %s", decision.Action)
	}
	if !decision.RiskLevelOverridden {
		t.Fatalf("expected RiskLevelOverridden=true")
	}
	if decision.DeclaredRiskLevel != "LOW" || decision.EffectiveRiskLevel != "IRREVERSIBLE" {
		t.Fatalf("expected declared=LOW effective=IRREVERSIBLE, got declared=%s effective=%s",
			decision.DeclaredRiskLevel, decision.EffectiveRiskLevel)
	}
}

// TestEvaluateToolCatalogUnknownToolUsesDeclaredRisk documents the trust
// boundary for tools that aren't registered: they fall back to whatever
// risk_level the caller declared, unchanged.
func TestEvaluateToolCatalogUnknownToolUsesDeclaredRisk(t *testing.T) {
	eng := engine.New()
	pack := models.PolicyPack{
		ID:      "default",
		Version: "0.2.0",
		ToolRules: []models.PolicyRule{
			{
				ID: "irreversible", Name: "Irreversible",
				CEL: "tool_call.risk_level == 'IRREVERSIBLE'", Action: models.ActionEscalateToJudge, Enabled: true,
			},
		},
		ToolCatalog: []models.ToolCatalogEntry{
			{ToolName: "delete_database", RiskLevel: "IRREVERSIBLE"},
		},
		Settings: models.PolicySettings{DefaultAction: models.ActionAllow},
	}

	call := models.ToolCallRequest{ToolName: "search_docs", RiskLevel: "LOW"}
	decision, err := eng.EvaluateTool(pack, "default", call, models.ModeEnforce)
	if err != nil {
		t.Fatalf("EvaluateTool: %v", err)
	}
	if decision.Action != models.ActionAllow {
		t.Fatalf("expected allow for unregistered low-risk tool, got %s", decision.Action)
	}
	if decision.RiskLevelOverridden {
		t.Fatalf("expected no override for unregistered tool")
	}
}
