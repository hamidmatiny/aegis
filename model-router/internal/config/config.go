package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"

	"github.com/aegis-platform/aegis/model-router/internal/provider"
)

// Config is the model-router runtime configuration.
type Config struct {
	Providers map[string]ProviderEntry `yaml:"providers"`
	Routing   RoutingConfig            `yaml:"routing"`
	Retry     RetryConfig              `yaml:"retry"`
}

// ProviderEntry describes a single upstream in config YAML.
type ProviderEntry struct {
	Enabled      bool              `yaml:"enabled"`
	BaseURL      string            `yaml:"base_url"`
	APIKeyEnv    string            `yaml:"api_key_env"`
	DefaultModel string            `yaml:"default_model"`
	ExtraHeaders map[string]string `yaml:"extra_headers,omitempty"`
}

// RoutingConfig controls default provider selection and fallback chain.
type RoutingConfig struct {
	DefaultProvider string        `yaml:"default_provider"`
	DefaultModel    string        `yaml:"default_model"`
	FallbackChain   []RouteTarget `yaml:"fallback_chain"`
}

// RouteTarget is one step in the fallback chain.
type RouteTarget struct {
	Provider string `yaml:"provider"`
	Model    string `yaml:"model,omitempty"`
}

// RetryConfig controls per-provider retry behaviour.
type RetryConfig struct {
	MaxAttempts int `yaml:"max_attempts"`
	BackoffMS   int `yaml:"backoff_ms"`
}

// Load reads configuration from a YAML file and applies environment overrides.
func Load(path string) (Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Config{}, fmt.Errorf("read config: %w", err)
	}
	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return Config{}, fmt.Errorf("parse config: %w", err)
	}
	cfg.applyDefaults()
	cfg.ApplyEnvOverrides()
	return cfg, nil
}

func (c *Config) applyDefaults() {
	if c.Retry.MaxAttempts == 0 {
		c.Retry.MaxAttempts = 3
	}
	if c.Retry.BackoffMS == 0 {
		c.Retry.BackoffMS = 300
	}
	if c.Routing.DefaultProvider == "" {
		c.Routing.DefaultProvider = "mock"
	}
	if c.Routing.DefaultModel == "" {
		c.Routing.DefaultModel = "mock-model"
	}
}

// BuildRegistry instantiates enabled providers from config.
func (c *Config) BuildRegistry(reg *provider.Registry) (map[string]provider.Provider, error) {
	providers := make(map[string]provider.Provider)
	for id, entry := range c.Providers {
		if !entry.Enabled {
			continue
		}
		p, err := reg.Build(provider.ProviderConfig{
			ID:           id,
			BaseURL:      entry.BaseURL,
			APIKeyEnv:    entry.APIKeyEnv,
			Enabled:      entry.Enabled,
			DefaultModel: entry.DefaultModel,
			ExtraHeaders: entry.ExtraHeaders,
		})
		if err != nil {
			return nil, fmt.Errorf("provider %q: %w", id, err)
		}
		providers[id] = p
	}
	if len(providers) == 0 {
		p, err := reg.Build(provider.ProviderConfig{ID: "mock", Enabled: true, DefaultModel: "mock-model"})
		if err != nil {
			return nil, err
		}
		providers["mock"] = p
	}
	return providers, nil
}

// ResolveChain returns ordered provider/model targets for a request.
func (c *Config) ResolveChain(reqProvider, reqModel string) []provider.RouteTarget {
	primaryProvider := reqProvider
	if primaryProvider == "" {
		primaryProvider = c.Routing.DefaultProvider
	}
	primaryModel := reqModel
	if primaryModel == "" {
		primaryModel = c.Routing.DefaultModel
		if entry, ok := c.Providers[primaryProvider]; ok && entry.DefaultModel != "" {
			primaryModel = entry.DefaultModel
		}
	}

	seen := make(map[string]bool)
	var chain []provider.RouteTarget
	add := func(providerID, model string) {
		key := providerID + "|" + model
		if seen[key] || providerID == "" {
			return
		}
		seen[key] = true
		chain = append(chain, provider.RouteTarget{Provider: providerID, Model: model})
	}

	add(primaryProvider, primaryModel)
	for _, fb := range c.Routing.FallbackChain {
		model := fb.Model
		if model == "" {
			if entry, ok := c.Providers[fb.Provider]; ok {
				model = entry.DefaultModel
			}
		}
		add(fb.Provider, model)
	}
	return chain
}

// ConfigPath resolves the config file path from env or default.
func ConfigPath() string {
	if p := os.Getenv("AEGIS_MODEL_ROUTER_CONFIG"); p != "" {
		return p
	}
	return filepath.Join("config", "providers.yaml")
}

// ApplyEnvOverrides patches config from well-known environment variables.
func (c *Config) ApplyEnvOverrides() {
	if v := os.Getenv("OLLAMA_BASE_URL"); v != "" {
		if e, ok := c.Providers["ollama"]; ok {
			e.BaseURL = strings.TrimRight(v, "/")
			c.Providers["ollama"] = e
		}
	}
}
