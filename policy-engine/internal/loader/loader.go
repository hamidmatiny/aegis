package loader

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"gopkg.in/yaml.v3"

	"github.com/aegis-platform/aegis/policy-engine/internal/models"
)

// Store loads and resolves versioned policy packs with per-tenant overrides.
type Store struct {
	mu        sync.RWMutex
	baseDir   string
	basePacks map[string]models.PolicyPack
	tenants   map[string]models.PolicyPack
}

// NewStore loads all policy packs from baseDir (typically ./policies).
func NewStore(baseDir string) (*Store, error) {
	s := &Store{
		baseDir:   baseDir,
		basePacks: make(map[string]models.PolicyPack),
		tenants:   make(map[string]models.PolicyPack),
	}
	if err := s.Reload(); err != nil {
		return nil, err
	}
	return s, nil
}

// Reload rescans policy YAML files (hot-reload entry point).
func (s *Store) Reload() error {
	basePacks := make(map[string]models.PolicyPack)
	tenantPacks := make(map[string]models.PolicyPack)

	entries, err := os.ReadDir(s.baseDir)
	if err != nil {
		return fmt.Errorf("read policy dir: %w", err)
	}
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		if !strings.HasSuffix(entry.Name(), ".yaml") && !strings.HasSuffix(entry.Name(), ".yml") {
			continue
		}
		path := filepath.Join(s.baseDir, entry.Name())
		pack, err := loadPackFile(path)
		if err != nil {
			return err
		}
		normalizePack(&pack)
		basePacks[pack.ID] = pack
	}

	tenantRoot := filepath.Join(s.baseDir, "tenants")
	if info, err := os.Stat(tenantRoot); err == nil && info.IsDir() {
		tenantDirs, err := os.ReadDir(tenantRoot)
		if err != nil {
			return fmt.Errorf("read tenants dir: %w", err)
		}
		for _, td := range tenantDirs {
			if !td.IsDir() {
				continue
			}
			tenantID := td.Name()
			tenantDir := filepath.Join(tenantRoot, tenantID)
			tfiles, err := os.ReadDir(tenantDir)
			if err != nil {
				return err
			}
			for _, tf := range tfiles {
				if tf.IsDir() {
					continue
				}
				if !strings.HasSuffix(tf.Name(), ".yaml") && !strings.HasSuffix(tf.Name(), ".yml") {
					continue
				}
				path := filepath.Join(tenantDir, tf.Name())
				pack, err := loadPackFile(path)
				if err != nil {
					return err
				}
				pack.TenantID = tenantID
				normalizePack(&pack)
				tenantPacks[tenantID] = pack
			}
		}
	}

	s.mu.Lock()
	s.basePacks = basePacks
	s.tenants = tenantPacks
	s.mu.Unlock()
	return nil
}

// ListBasePacks returns loaded base policy packs.
func (s *Store) ListBasePacks() []models.PolicyPack {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]models.PolicyPack, 0, len(s.basePacks))
	for _, p := range s.basePacks {
		out = append(out, p)
	}
	return out
}

// Resolve returns the effective policy pack for a tenant, merging overrides.
func (s *Store) Resolve(tenantID, packID string) (models.PolicyPack, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if packID == "" {
		packID = "default"
	}

	base, ok := s.basePacks[packID]
	if !ok {
		return models.PolicyPack{}, fmt.Errorf("policy pack %q not found", packID)
	}

	effective := clonePack(base)
	if tenantID == "" || tenantID == "default" {
		return effective, nil
	}

	override, ok := s.tenants[tenantID]
	if !ok {
		return effective, nil
	}

	return mergePacks(effective, override), nil
}

func loadPackFile(path string) (models.PolicyPack, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return models.PolicyPack{}, fmt.Errorf("read %s: %w", path, err)
	}
	var pack models.PolicyPack
	if err := yaml.Unmarshal(data, &pack); err != nil {
		return models.PolicyPack{}, fmt.Errorf("parse %s: %w", path, err)
	}
	return pack, nil
}

func normalizePack(p *models.PolicyPack) {
	if p.TenantID == "" {
		p.TenantID = "default"
	}
	if p.Settings.DefaultAction == "" {
		p.Settings.DefaultAction = models.ActionAllow
	}
	for i := range p.InputRules {
		if p.InputRules[i].Action == "" {
			p.InputRules[i].Action = models.ActionBlock
		}
	}
	for i := range p.OutputRules {
		if p.OutputRules[i].Action == "" {
			p.OutputRules[i].Action = models.ActionBlock
		}
	}
	for i := range p.ToolRules {
		if p.ToolRules[i].Action == "" {
			p.ToolRules[i].Action = models.ActionBlock
		}
	}
}

func clonePack(p models.PolicyPack) models.PolicyPack {
	out := p
	out.InputRules = append([]models.PolicyRule(nil), p.InputRules...)
	out.OutputRules = append([]models.PolicyRule(nil), p.OutputRules...)
	out.ToolRules = append([]models.PolicyRule(nil), p.ToolRules...)
	out.Overrides = append([]models.RuleOverride(nil), p.Overrides...)
	return out
}

func mergePacks(base, override models.PolicyPack) models.PolicyPack {
	result := clonePack(base)
	result.TenantID = override.TenantID

	if override.Extends != "" && override.Extends != base.ID {
		// Tenant file may declare a different base; caller resolved base already.
	}

	// Apply explicit rule disable/enable overrides from tenant pack.
	if len(override.Overrides) > 0 {
		applyRuleOverrides(&result.InputRules, override.Overrides)
		applyRuleOverrides(&result.OutputRules, override.Overrides)
		applyRuleOverrides(&result.ToolRules, override.Overrides)
	}

	// Append or replace tenant-specific rules by ID.
	result.InputRules = mergeRules(result.InputRules, override.InputRules)
	result.OutputRules = mergeRules(result.OutputRules, override.OutputRules)
	result.ToolRules = mergeRules(result.ToolRules, override.ToolRules)

	if override.Settings.DefaultAction != "" {
		result.Settings.DefaultAction = override.Settings.DefaultAction
	}
	if override.Version != "" {
		result.Version = override.Version
	}
	if override.Description != "" {
		result.Description = override.Description
	}
	return result
}

func applyRuleOverrides(rules *[]models.PolicyRule, overrides []models.RuleOverride) {
	idx := make(map[string]int, len(*rules))
	for i, r := range *rules {
		idx[r.ID] = i
	}
	for _, o := range overrides {
		if i, ok := idx[o.ID]; ok && o.Enabled != nil {
			(*rules)[i].Enabled = *o.Enabled
		}
	}
}

func mergeRules(base []models.PolicyRule, extra []models.PolicyRule) []models.PolicyRule {
	if len(extra) == 0 {
		return base
	}
	idx := make(map[string]int, len(base))
	for i, r := range base {
		idx[r.ID] = i
	}
	out := append([]models.PolicyRule(nil), base...)
	for _, rule := range extra {
		if i, ok := idx[rule.ID]; ok {
			out[i] = rule
		} else {
			out = append(out, rule)
			idx[rule.ID] = len(out) - 1
		}
	}
	return out
}
