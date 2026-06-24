package taint

import (
	"github.com/aegis-platform/aegis/agent-gate/internal/models"
)

// CollectLabels aggregates taint labels from arguments and call-level metadata.
func CollectLabels(call models.ToolCallRequest) []models.TaintLabel {
	labels := append([]models.TaintLabel{}, call.TaintLabels...)
	seen := map[string]bool{}
	for _, l := range labels {
		seen[l.Source+":"+l.Field] = true
	}

	for _, arg := range call.Arguments {
		if arg.TaintLevel == "" || arg.TaintLevel == models.TaintTrusted {
			continue
		}
		source := arg.TaintSource
		if source == "" {
			source = "ARGUMENT"
		}
		key := source + ":" + arg.Name
		if seen[key] {
			continue
		}
		seen[key] = true
		labels = append(labels, models.TaintLabel{
			Source: source,
			Level:  arg.TaintLevel,
			Field:  arg.Name,
		})
	}
	return labels
}

// FlaggedTaint returns labels for arguments that are tainted or carry credentials.
func FlaggedTaint(args []models.ToolArgument) []models.TaintLabel {
	var out []models.TaintLabel
	for _, arg := range args {
		if arg.TaintLevel == models.TaintTainted || arg.ContainsCredentials {
			source := arg.TaintSource
			if source == "" {
				source = "ARGUMENT"
			}
			out = append(out, models.TaintLabel{
				Source: source,
				Level:  arg.TaintLevel,
				Field:  arg.Name,
			})
		}
	}
	return out
}

// DefaultRiskLevel returns LOW when unset.
func DefaultRiskLevel(level string) string {
	if level == "" {
		return "LOW"
	}
	return level
}
