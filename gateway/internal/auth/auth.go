// Package auth provides API key authentication for the gateway's public
// HTTP surface. The gateway is the single ingress point for AEGIS
// (Application -> SDK/Reverse Proxy -> Gateway -> internal services), so key
// enforcement lives here rather than on every internal service.
package auth

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"net/http"
	"os"
	"strings"
)

// Source describes where the active API key set came from.
type Source string

const (
	// SourceConfigured means keys were read from AEGIS_API_KEYS.
	SourceConfigured Source = "configured"
	// SourceGenerated means no keys were configured, so the gateway
	// generated a single ephemeral key for this process's lifetime.
	SourceGenerated Source = "generated"
)

// Config holds the active API key set for the running gateway process.
type Config struct {
	Keys   map[string]struct{}
	Source Source
	// GeneratedKey is set only when Source == SourceGenerated, so the
	// caller can log it once at startup. It is never re-derivable later.
	GeneratedKey string
}

// EnvKeys is the environment variable holding a comma-separated list of
// valid API keys.
const EnvKeys = "AEGIS_API_KEYS"

// Load reads AEGIS_API_KEYS from the environment. If it is unset or empty,
// the gateway refuses to start wide open: it generates a single random key
// that is valid for this process's lifetime and must be read from the
// startup log. This means there is never a static, guessable default.
func Load() Config {
	raw := os.Getenv(EnvKeys)
	if raw != "" {
		keys := map[string]struct{}{}
		for _, k := range strings.Split(raw, ",") {
			k = strings.TrimSpace(k)
			if k != "" {
				keys[k] = struct{}{}
			}
		}
		if len(keys) > 0 {
			return Config{Keys: keys, Source: SourceConfigured}
		}
	}
	gen := GenerateKey()
	return Config{
		Keys:         map[string]struct{}{gen: {}},
		Source:       SourceGenerated,
		GeneratedKey: gen,
	}
}

// GenerateKey returns a fresh, cryptographically random API key.
func GenerateKey() string {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		// crypto/rand failing means the OS RNG is broken; there is no safe
		// way to continue serving a security-sensitive proxy at that point.
		panic("auth: failed to generate API key: " + err.Error())
	}
	return "aegis_" + hex.EncodeToString(b)
}

// Valid reports whether key matches one of the configured keys. Comparison
// is constant-time per candidate key to avoid leaking timing information.
func (c Config) Valid(key string) bool {
	if key == "" {
		return false
	}
	ok := false
	for k := range c.Keys {
		if subtle.ConstantTimeCompare([]byte(k), []byte(key)) == 1 {
			ok = true
		}
	}
	return ok
}

// exemptPaths never require an API key: liveness/readiness probes must stay
// reachable for container orchestration health checks.
var exemptPaths = map[string]struct{}{
	"/health": {},
	"/ready":  {},
}

// Middleware enforces API key auth on every request except exemptPaths.
// Keys may be supplied as "Authorization: Bearer <key>" (OpenAI-SDK
// compatible, since the gateway is an OpenAI-compatible reverse proxy) or
// "X-API-Key: <key>".
func Middleware(cfg Config) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if _, exempt := exemptPaths[r.URL.Path]; exempt {
				next.ServeHTTP(w, r)
				return
			}
			if !cfg.Valid(extractKey(r)) {
				writeUnauthorized(w)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

func extractKey(r *http.Request) string {
	if h := r.Header.Get("Authorization"); h != "" {
		if rest, ok := strings.CutPrefix(h, "Bearer "); ok {
			return rest
		}
		return h
	}
	return r.Header.Get("X-API-Key")
}

func writeUnauthorized(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	_, _ = w.Write([]byte(`{"error":{"type":"aegis_unauthorized","message":"missing or invalid API key. Send it as \"Authorization: Bearer <key>\" or \"X-API-Key: <key>\"."}}`))
}
