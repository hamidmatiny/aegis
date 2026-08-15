// Package auth provides API key authentication for agent-gate, with two
// distinct credential scopes.
//
// Why two scopes: agent-gate's whole value proposition is that an
// irreversible tool call ("delete_database") waits for a *human* decision
// via POST /v1/approvals/{id}/decide before it is allowed to proceed. If
// the same credential that lets a calling agent submit a tool call also
// lets it decide the resulting approval, that guarantee is fiction — the
// calling agent (or whatever compromised or hallucinating logic is driving
// it) can immediately approve its own irreversible action. So the decide
// endpoint requires a separate reviewer key that a calling agent's service
// key does not satisfy.
package auth

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"net/http"
	"os"
	"strings"
)

// Source describes where an active key set came from.
type Source string

const (
	// SourceConfigured means keys were read from the environment.
	SourceConfigured Source = "configured"
	// SourceGenerated means no keys were configured, so agent-gate
	// generated a single ephemeral key for this process's lifetime.
	SourceGenerated Source = "generated"
)

// EnvServiceKeys holds the comma-separated keys allowed to call
// POST /v1/evaluate and read approvals (the calling-agent / integration
// credential).
const EnvServiceKeys = "AEGIS_AGENT_GATE_API_KEYS"

// EnvReviewerKeys holds the comma-separated keys allowed to decide a
// pending approval. Deliberately separate from EnvServiceKeys.
const EnvReviewerKeys = "AEGIS_AGENT_GATE_REVIEWER_KEYS"

// KeySet is a single named set of valid API keys.
type KeySet struct {
	Name         string
	Keys         map[string]struct{}
	Source       Source
	GeneratedKey string
}

// Config holds both credential scopes for a running agent-gate process.
type Config struct {
	Service  KeySet
	Reviewer KeySet
}

// Load reads both key sets from the environment. Either one that is unset
// gets a fresh ephemeral key generated for this process's lifetime — there
// is never a static, guessable default, and the two scopes are never
// derived from each other.
func Load() Config {
	return Config{
		Service:  loadKeySet(EnvServiceKeys, "service"),
		Reviewer: loadKeySet(EnvReviewerKeys, "reviewer"),
	}
}

func loadKeySet(envVar, name string) KeySet {
	raw := os.Getenv(envVar)
	if raw != "" {
		keys := map[string]struct{}{}
		for _, k := range strings.Split(raw, ",") {
			k = strings.TrimSpace(k)
			if k != "" {
				keys[k] = struct{}{}
			}
		}
		if len(keys) > 0 {
			return KeySet{Name: name, Keys: keys, Source: SourceConfigured}
		}
	}
	gen := GenerateKey()
	return KeySet{
		Name:         name,
		Keys:         map[string]struct{}{gen: {}},
		Source:       SourceGenerated,
		GeneratedKey: gen,
	}
}

// GenerateKey returns a fresh, cryptographically random API key.
func GenerateKey() string {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		panic("auth: failed to generate API key: " + err.Error())
	}
	return "aegis_" + hex.EncodeToString(b)
}

// Fingerprint returns a short, non-reversible identifier for a key --
// never the key itself, and not usable to reconstruct it (SHA-256 of a
// high-entropy 256-bit key, truncated to 48 bits of output is more than
// enough to distinguish a small number of operator-configured keys from
// each other without leaking anything about the original secret).
//
// Used to correlate agent identity claims (agent_id, entirely
// caller-declared and unverified) against which actual credential
// authenticated the request -- see the Stage E.1/E.2 note on
// contextKeyFingerprint below for why this exists.
func Fingerprint(key string) string {
	sum := sha256.Sum256([]byte(key))
	return hex.EncodeToString(sum[:])[:12]
}

type contextKey int

// contextKeyFingerprint carries the Fingerprint of whichever Service key
// authenticated the current request, set by Middleware and read by
// handlers that want to record it (agent-gate's tool-gate audit emission
// does, so the audit trail can later reveal when a single agent_id is
// claimed under multiple different keys, or a single key claims many
// different agent_id values -- neither is enforced here, since this
// project's shared-key-per-integration model doesn't support strict
// per-agent credential binding without a bigger architecture change; this
// is a detection signal for scripts/asi07-identity-consistency-query.py,
// not a new authorization check).
const contextKeyFingerprint contextKey = iota

// ContextWithFingerprint returns a context carrying the given key
// fingerprint, retrievable later via FingerprintFromContext.
func ContextWithFingerprint(ctx context.Context, fingerprint string) context.Context {
	return context.WithValue(ctx, contextKeyFingerprint, fingerprint)
}

// FingerprintFromContext returns the fingerprint set by ContextWithFingerprint,
// or "" if none was set (e.g. an exempt path, or a request that was never
// authenticated with a Service key at all).
func FingerprintFromContext(ctx context.Context) string {
	v, _ := ctx.Value(contextKeyFingerprint).(string)
	return v
}

// Valid reports whether key matches one of this set's keys, using a
// constant-time comparison per candidate to avoid leaking timing info.
func (ks KeySet) Valid(key string) bool {
	if key == "" {
		return false
	}
	ok := false
	for k := range ks.Keys {
		if subtle.ConstantTimeCompare([]byte(k), []byte(key)) == 1 {
			ok = true
		}
	}
	return ok
}

var exemptPaths = map[string]struct{}{
	"/health": {},
	"/ready":  {},
}

// isDecideRequest matches the same route handleApprovals treats as a
// decide call: POST /v1/approvals/{id}/decide.
func isDecideRequest(r *http.Request) bool {
	if r.Method != http.MethodPost {
		return false
	}
	path := strings.TrimPrefix(r.URL.Path, "/v1/approvals/")
	if path == r.URL.Path {
		return false
	}
	parts := strings.Split(strings.Trim(path, "/"), "/")
	return len(parts) == 2 && parts[1] == "decide"
}

// Middleware enforces API key auth on every request except exemptPaths.
// Requests to the decide route must present a Reviewer key; every other
// non-exempt request must present a Service key. A valid Service key alone
// does not satisfy a decide request, and vice versa.
func Middleware(cfg Config) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if _, exempt := exemptPaths[r.URL.Path]; exempt {
				next.ServeHTTP(w, r)
				return
			}

			key := extractKey(r)
			if isDecideRequest(r) {
				if !cfg.Reviewer.Valid(key) {
					writeUnauthorized(w, "missing or invalid reviewer API key. Deciding an approval requires a "+
						"reviewer key (AEGIS_AGENT_GATE_REVIEWER_KEYS), not the service key used to submit tool "+
						"calls — a calling agent cannot approve its own irreversible action.")
					return
				}
				next.ServeHTTP(w, r)
				return
			}

			if !cfg.Service.Valid(key) {
				writeUnauthorized(w, "missing or invalid API key. Send it as \"Authorization: Bearer <key>\" or "+
					"\"X-API-Key: <key>\".")
				return
			}
			r = r.WithContext(ContextWithFingerprint(r.Context(), Fingerprint(key)))
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

func writeUnauthorized(w http.ResponseWriter, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	_, _ = w.Write([]byte(`{"error":{"type":"aegis_unauthorized","message":"` + escapeJSON(message) + `"}}`))
}

func escapeJSON(s string) string {
	s = strings.ReplaceAll(s, `\`, `\\`)
	s = strings.ReplaceAll(s, `"`, `\"`)
	return s
}
