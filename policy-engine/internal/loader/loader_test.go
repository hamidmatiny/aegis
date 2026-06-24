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
