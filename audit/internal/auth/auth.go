// Package auth enforces the shared internal service-to-service token on
// this service's HTTP surface. Unlike the gateway's per-tenant
// AEGIS_API_KEYS (internal/auth in gateway), this is a single secret
// shared by every internal-only service and the handful of processes
// that call them (gateway, agent-gate, policy-engine, input-defense,
// output-defense, redteam, the dashboard's nginx proxy) — see
// scripts/generate-credentials.sh and docker-compose.yml's
// AEGIS_INTERNAL_TOKEN. This service was previously reachable with no
// auth at all to anything that could reach it on the Docker network.
package auth

import (
	"crypto/subtle"
	"net/http"
	"strings"
)

// EnvToken is the environment variable holding the shared internal token.
const EnvToken = "AEGIS_INTERNAL_TOKEN"

// exemptPaths never require the internal token: liveness/readiness probes
// must stay reachable for container orchestration health checks.
var exemptPaths = map[string]struct{}{
	"/health": {},
	"/ready":  {},
}

// Middleware enforces the shared internal token on every request except
// exemptPaths. token must be non-empty — callers should refuse to start
// the server at all if AEGIS_INTERNAL_TOKEN is unset (see main.go) rather
// than fall back to an ephemeral per-process token, since that would
// desync every other service's copy of the same shared secret.
func Middleware(token string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if _, exempt := exemptPaths[r.URL.Path]; exempt {
				next.ServeHTTP(w, r)
				return
			}
			if !valid(token, extractToken(r)) {
				writeUnauthorized(w)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

// valid reports whether candidate matches the configured token, compared
// in constant time to avoid leaking timing information.
func valid(configured, candidate string) bool {
	if configured == "" || candidate == "" {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(configured), []byte(candidate)) == 1
}

// extractToken reads the token from "Authorization: Bearer <token>" (the
// convention every other AEGIS auth surface uses) or, as a fallback,
// "X-Aegis-Internal-Token: <token>" for any caller that can't safely set
// Authorization (e.g. a proxy already using that header for a different
// downstream credential on a different route).
func extractToken(r *http.Request) string {
	if h := r.Header.Get("Authorization"); h != "" {
		if rest, ok := strings.CutPrefix(h, "Bearer "); ok {
			return rest
		}
		return h
	}
	return r.Header.Get("X-Aegis-Internal-Token")
}

func writeUnauthorized(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	_, _ = w.Write([]byte(`{"error":{"type":"aegis_unauthorized","message":"missing or invalid internal service token. Send it as \"Authorization: Bearer <token>\" or \"X-Aegis-Internal-Token: <token>\"."}}`))
}
