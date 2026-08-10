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
