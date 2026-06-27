package provider

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
)

// ResolveAPIKey reads the provider key from the process environment at call time.
// Keys are never baked into images or config files — only api_key_env names are stored.
func ResolveAPIKey(cfg ProviderConfig) string {
	if cfg.APIKeyEnv != "" {
		if v := os.Getenv(cfg.APIKeyEnv); v != "" {
			return v
		}
	}
	return cfg.APIKey
}

// APIKeyFingerprint returns a non-secret identifier for logs and /v1/providers.
func APIKeyFingerprint(key string) string {
	if key == "" {
		return ""
	}
	if len(key) <= 8 {
		sum := sha256.Sum256([]byte(key))
		return "sha256:" + hex.EncodeToString(sum[:4])
	}
	return "…" + key[len(key)-4:]
}
