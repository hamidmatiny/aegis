package engine

import (
	"strings"

	"github.com/aegis-platform/aegis/policy-engine/internal/models"
)

// riskRank orders risk levels from least to most restrictive. Unknown or
// empty values rank as LOW so an unrecognized level can never silently
// outrank a real one.
var riskRank = map[string]int{
	"LOW":          0,
	"MEDIUM":       1,
	"HIGH":         2,
	"IRREVERSIBLE": 3,
}

func rankOf(level string) int {
	if r, ok := riskRank[strings.ToUpper(level)]; ok {
		return r
	}
	return 0
}

// resolveToolRisk determines the risk level actually used for policy
// evaluation. A tool_call's risk_level is supplied by whoever assembles the
// call — which, in a real agent integration, may ultimately be influenced
// by the LLM's own output. It is never sufficient on its own to prove a
// call is low-risk.
//
// If the tool is registered in the pack's tool_catalog, the catalog's risk
// level is the operator-set floor: the effective risk is the higher-ranked
// of (declared, catalog). A catalogued IRREVERSIBLE tool therefore always
// evaluates as IRREVERSIBLE, even if the caller declares LOW. Tools absent
// from the catalog fall back to the caller's declared risk level unchanged
// (documented trust boundary — register your dangerous tools).
func resolveToolRisk(pack models.PolicyPack, call models.ToolCallRequest) (effective string, overridden bool) {
	declared := call.RiskLevel
	if declared == "" {
		declared = "LOW"
	}

	for _, entry := range pack.ToolCatalog {
		if strings.EqualFold(entry.ToolName, call.ToolName) {
			if rankOf(entry.RiskLevel) > rankOf(declared) {
				return entry.RiskLevel, true
			}
			return declared, false
		}
	}

	return declared, false
}
