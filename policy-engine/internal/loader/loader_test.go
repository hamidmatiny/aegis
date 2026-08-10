package loader_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/aegis-platform/aegis/policy-engine/internal/loader"
	"github.com/aegis-platform/aegis/policy-engine/internal/models"
)

func TestResolveDefaultPack(t *testing.T) {
	dir := testPolicyDir(t)
	store, err := loader.NewStore(dir)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}
	pack, err := store.Resolve("default", "default")
	if err != nil {
		t.Fatalf("Resolve: %v", err)
	}
	if pack.ID != "default" {
		t.Fatalf("expected default pack, got %s", pack.ID)
	}
	if len(pack.InputRules) == 0 {
		t.Fatal("expected input rules")
	}
}

func TestTenantOverrideStricter(t *testing.T) {
	dir := testPolicyDir(t)
	store, err := loader.NewStore(dir)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}
	base, err := store.Resolve("default", "default")
	if err != nil {
		t.Fatalf("Resolve default: %v", err)
	}
	acme, err := store.Resolve("acme", "default")
	if err != nil {
		t.Fatalf("Resolve acme: %v", err)
	}
	if len(acme.InputRules) <= len(base.InputRules) {
		t.Fatalf("expected acme to have at least as many input rules as base")
	}
	found := false
	for _, r := range acme.InputRules {
		if r.ID == "acme-block-moderate-fusion" {
			found = true
		}
	}
	if !found {
		t.Fatal("expected acme-specific rule")
	}
	// escalate-ambiguous-input should be disabled via override
	for _, r := range acme.InputRules {
		if r.ID == "escalate-ambiguous-input" && r.Enabled {
			t.Fatal("expected escalate-ambiguous-input disabled for acme")
		}
	}
}

func TestToolCatalogMerge(t *testing.T) {
	root := t.TempDir()
	baseYAML := `
id: default
version: "0.2.0"
tenant_id: default
tool_catalog:
  - tool_name: delete_database
    risk_level: IRREVERSIBLE
  - tool_name: send_email
    risk_level: MEDIUM
settings:
  default_action: allow
`
	if err := os.WriteFile(filepath.Join(root, "default.yaml"), []byte(baseYAML), 0o644); err != nil {
		t.Fatal(err)
	}
	acmeDir := filepath.Join(root, "tenants", "acme")
	if err := os.MkdirAll(acmeDir, 0o755); err != nil {
		t.Fatal(err)
	}
	// ACME registers its own tool and tightens send_email to IRREVERSIBLE.
	acmeYAML := `
extends: default
id: default
version: "0.2.0-acme"
tenant_id: acme
tool_catalog:
  - tool_name: send_email
    risk_level: IRREVERSIBLE
  - tool_name: wipe_cluster
    risk_level: IRREVERSIBLE
settings:
  default_action: allow
`
	if err := os.WriteFile(filepath.Join(acmeDir, "overrides.yaml"), []byte(acmeYAML), 0o644); err != nil {
		t.Fatal(err)
	}

	store, err := loader.NewStore(root)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}

	base, err := store.Resolve("default", "default")
	if err != nil {
		t.Fatalf("Resolve default: %v", err)
	}
	if len(base.ToolCatalog) != 2 {
		t.Fatalf("expected 2 base catalog entries, got %d", len(base.ToolCatalog))
	}

	acme, err := store.Resolve("acme", "default")
	if err != nil {
		t.Fatalf("Resolve acme: %v", err)
	}
	if len(acme.ToolCatalog) != 3 {
		t.Fatalf("expected 3 merged catalog entries (delete_database + overridden send_email + wipe_cluster), got %d", len(acme.ToolCatalog))
	}
	byName := map[string]string{}
	for _, e := range acme.ToolCatalog {
		byName[e.ToolName] = e.RiskLevel
	}
	if byName["send_email"] != "IRREVERSIBLE" {
		t.Fatalf("expected acme override of send_email to IRREVERSIBLE, got %s", byName["send_email"])
	}
	if byName["delete_database"] != "IRREVERSIBLE" {
		t.Fatalf("expected inherited delete_database entry, got %s", byName["delete_database"])
	}
	if byName["wipe_cluster"] != "IRREVERSIBLE" {
		t.Fatalf("expected acme-added wipe_cluster entry, got %s", byName["wipe_cluster"])
	}
}

func testPolicyDir(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	defaultYAML := `
id: default
version: "0.2.0"
tenant_id: default
input_rules:
  - id: block-high-fusion-score
    name: Block high
    cel: "input_verdict.fused_score >= 0.85"
    action: block
    enabled: true
  - id: escalate-ambiguous-input
    name: Escalate ambiguous
    cel: "input_verdict.fused_score >= 0.55 && input_verdict.fused_score < 0.85"
    action: escalate_to_judge
    enabled: true
settings:
  default_action: allow
`
	if err := os.WriteFile(filepath.Join(root, "default.yaml"), []byte(defaultYAML), 0o644); err != nil {
		t.Fatal(err)
	}
	acmeDir := filepath.Join(root, "tenants", "acme")
	if err := os.MkdirAll(acmeDir, 0o755); err != nil {
		t.Fatal(err)
	}
	acmeYAML := `
extends: default
id: default
version: "0.2.0-acme"
tenant_id: acme
overrides:
  - id: escalate-ambiguous-input
    enabled: false
input_rules:
  - id: acme-block-moderate-fusion
    name: ACME moderate block
    cel: "input_verdict.fused_score >= 0.45"
    action: block
    enabled: true
settings:
  default_action: allow
`
	if err := os.WriteFile(filepath.Join(acmeDir, "overrides.yaml"), []byte(acmeYAML), 0o644); err != nil {
		t.Fatal(err)
	}
	return root
}

var _ = models.ActionAllow
