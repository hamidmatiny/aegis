package config

import "os"

// Config holds gateway downstream service URLs and runtime settings.
type Config struct {
	HTTPPort           string
	InputDefenseURL    string
	OutputDefenseURL   string
	PolicyEngineURL    string
	ModelRouterURL     string
	AgentGateURL       string
	DefaultTenantID    string
	DefaultModel       string
	HTTPTimeoutSeconds int
	// InternalToken authenticates the gateway's own outbound calls to
	// input-defense, output-defense, and policy-engine, all of which now
	// reject unauthenticated requests. Read directly (no fallback/default)
	// so a missing value fails loudly via the startup check in main.go
	// rather than silently sending unauthenticated requests that 401.
	InternalToken string
}

// Load reads configuration from environment variables.
func Load() Config {
	return Config{
		HTTPPort:           envOr("AEGIS_GATEWAY_HTTP_PORT", "8080"),
		InputDefenseURL:    trimSlash(envOr("AEGIS_INPUT_DEFENSE_URL", "http://localhost:8090")),
		OutputDefenseURL:   trimSlash(envOr("AEGIS_OUTPUT_DEFENSE_URL", "http://localhost:8091")),
		PolicyEngineURL:    trimSlash(envOr("AEGIS_POLICY_ENGINE_URL", "http://localhost:8081")),
		ModelRouterURL:     trimSlash(envOr("AEGIS_MODEL_ROUTER_URL", "http://localhost:8082")),
		AgentGateURL:       trimSlash(envOr("AEGIS_AGENT_GATE_URL", "http://localhost:8083")),
		DefaultTenantID:    envOr("AEGIS_DEFAULT_TENANT_ID", "default"),
		DefaultModel:       envOr("AEGIS_DEFAULT_MODEL", "mock-model"),
		HTTPTimeoutSeconds: envInt("AEGIS_GATEWAY_HTTP_TIMEOUT", 120),
		InternalToken:      os.Getenv("AEGIS_INTERNAL_TOKEN"),
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		var n int
		for _, c := range v {
			if c < '0' || c > '9' {
				return fallback
			}
			n = n*10 + int(c-'0')
		}
		if n > 0 {
			return n
		}
	}
	return fallback
}

func trimSlash(s string) string {
	for len(s) > 0 && s[len(s)-1] == '/' {
		s = s[:len(s)-1]
	}
	return s
}
