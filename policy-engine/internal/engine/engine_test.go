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
