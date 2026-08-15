package auth_test

import (
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/aegis-platform/aegis/agent-gate/internal/auth"
)

func TestLoad_GeneratesDistinctKeysWhenUnset(t *testing.T) {
	t.Setenv(auth.EnvServiceKeys, "")
	t.Setenv(auth.EnvReviewerKeys, "")
	cfg := auth.Load()

	if cfg.Service.Source != auth.SourceGenerated || cfg.Reviewer.Source != auth.SourceGenerated {
		t.Fatalf("expected both scopes generated")
	}
	if cfg.Service.GeneratedKey == "" || cfg.Reviewer.GeneratedKey == "" {
		t.Fatalf("expected non-empty generated keys")
	}
	if cfg.Service.GeneratedKey == cfg.Reviewer.GeneratedKey {
		t.Fatalf("service and reviewer keys must never be equal")
	}
	if !cfg.Service.Valid(cfg.Service.GeneratedKey) {
		t.Fatalf("generated service key should validate against the service key set")
	}
	if !cfg.Reviewer.Valid(cfg.Reviewer.GeneratedKey) {
		t.Fatalf("generated reviewer key should validate against the reviewer key set")
	}
}

func TestLoad_UsesConfiguredKeys(t *testing.T) {
	t.Setenv(auth.EnvServiceKeys, "svc-one, svc-two")
	t.Setenv(auth.EnvReviewerKeys, "rev-one")
	cfg := auth.Load()

	if !cfg.Service.Valid("svc-one") || !cfg.Service.Valid("svc-two") {
		t.Fatalf("configured service keys should be valid")
	}
	if !cfg.Reviewer.Valid("rev-one") {
		t.Fatalf("configured reviewer key should be valid")
	}
}

func TestServiceKeyDoesNotSatisfyReviewerScope(t *testing.T) {
	t.Setenv(auth.EnvServiceKeys, "svc-key")
	t.Setenv(auth.EnvReviewerKeys, "rev-key")
	cfg := auth.Load()

	if cfg.Reviewer.Valid("svc-key") {
		t.Fatalf("a valid service key must not validate against the reviewer key set")
	}
	if cfg.Service.Valid("rev-key") {
		t.Fatalf("a valid reviewer key must not validate against the service key set")
	}
}

func newTestMux() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	mux.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	mux.HandleFunc("/v1/evaluate", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	mux.HandleFunc("/v1/approvals/", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	return mux
}

func testConfig() auth.Config {
	return auth.Config{
		Service:  auth.KeySet{Name: "service", Keys: map[string]struct{}{"svc-key": {}}, Source: auth.SourceConfigured},
		Reviewer: auth.KeySet{Name: "reviewer", Keys: map[string]struct{}{"rev-key": {}}, Source: auth.SourceConfigured},
	}
}

func TestMiddleware_ExemptsHealthAndReady(t *testing.T) {
	h := auth.Middleware(testConfig())(newTestMux())
	for _, path := range []string{"/health", "/ready"} {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: expected 200 without a key, got %d", path, rec.Code)
		}
	}
}

func TestMiddleware_EvaluateRequiresServiceKey(t *testing.T) {
	h := auth.Middleware(testConfig())(newTestMux())

	req := httptest.NewRequest(http.MethodPost, "/v1/evaluate", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 without a key, got %d", rec.Code)
	}

	req = httptest.NewRequest(http.MethodPost, "/v1/evaluate", nil)
	req.Header.Set("Authorization", "Bearer svc-key")
	rec = httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 with a valid service key, got %d", rec.Code)
	}
}

func TestMiddleware_DecideRejectsServiceKey(t *testing.T) {
	// This is the core regression test: the same credential a calling
	// agent uses to submit a tool call must NOT be able to approve the
	// resulting approval. Without this, "human approval required" is not
	// actually enforced.
	h := auth.Middleware(testConfig())(newTestMux())

	req := httptest.NewRequest(http.MethodPost, "/v1/approvals/appr-123/decide", nil)
	req.Header.Set("Authorization", "Bearer svc-key")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 when self-approving with a service key, got %d", rec.Code)
	}
}

func TestMiddleware_DecideAcceptsReviewerKey(t *testing.T) {
	h := auth.Middleware(testConfig())(newTestMux())

	req := httptest.NewRequest(http.MethodPost, "/v1/approvals/appr-123/decide", nil)
	req.Header.Set("Authorization", "Bearer rev-key")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 with a valid reviewer key, got %d", rec.Code)
	}
}

func TestMiddleware_ReviewerKeyDoesNotSatisfyEvaluate(t *testing.T) {
	h := auth.Middleware(testConfig())(newTestMux())

	req := httptest.NewRequest(http.MethodPost, "/v1/evaluate", nil)
	req.Header.Set("Authorization", "Bearer rev-key")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 submitting a tool call with only a reviewer key, got %d", rec.Code)
	}
}

func TestMiddleware_ApprovalsGetRequiresServiceKey(t *testing.T) {
	// Listing/reading approvals (dashboard inbox) uses the service scope,
	// distinct from deciding them.
	h := auth.Middleware(testConfig())(newTestMux())

	req := httptest.NewRequest(http.MethodGet, "/v1/approvals/appr-123", nil)
	req.Header.Set("Authorization", "Bearer svc-key")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 reading an approval with a service key, got %d", rec.Code)
	}
}

// TestFingerprint_DeterministicAndDistinct is the core property this
// whole feature (Stage E.2, ASI07 identity-consistency detection) relies
// on: the same key must always produce the same fingerprint (so an
// agent's established fingerprint baseline is stable across requests),
// different keys must produce different fingerprints (so it actually
// distinguishes identities), and the fingerprint must never just be the
// key itself or an obvious substring of it.
func TestFingerprint_DeterministicAndDistinct(t *testing.T) {
	a := auth.Fingerprint("svc-key-one")
	b := auth.Fingerprint("svc-key-one")
	c := auth.Fingerprint("svc-key-two")

	if a != b {
		t.Fatalf("expected the same key to produce the same fingerprint, got %q and %q", a, b)
	}
	if a == c {
		t.Fatalf("expected different keys to produce different fingerprints, both were %q", a)
	}
	if a == "svc-key-one" || strings.Contains(a, "svc-key-one") {
		t.Fatalf("fingerprint must not be or contain the original key, got %q", a)
	}
}

func TestMiddleware_SetsFingerprintInContextForServiceKey(t *testing.T) {
	var gotFingerprint string
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/evaluate", func(w http.ResponseWriter, r *http.Request) {
		gotFingerprint = auth.FingerprintFromContext(r.Context())
		w.WriteHeader(http.StatusOK)
	})
	h := auth.Middleware(testConfig())(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/evaluate", nil)
	req.Header.Set("Authorization", "Bearer svc-key")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	want := auth.Fingerprint("svc-key")
	if gotFingerprint != want {
		t.Fatalf("expected context fingerprint %q, got %q", want, gotFingerprint)
	}
}

func TestMiddleware_DoesNotSetFingerprintOnExemptPaths(t *testing.T) {
	var gotFingerprint string
	sawFingerprint := false
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		gotFingerprint = auth.FingerprintFromContext(r.Context())
		sawFingerprint = true
		w.WriteHeader(http.StatusOK)
	})
	h := auth.Middleware(testConfig())(mux)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if !sawFingerprint {
		t.Fatal("handler was not reached")
	}
	if gotFingerprint != "" {
		t.Fatalf("expected no fingerprint set on an exempt, unauthenticated path, got %q", gotFingerprint)
	}
}

func TestMain(m *testing.M) {
	if err := os.Unsetenv(auth.EnvServiceKeys); err != nil {
		panic(err)
	}
	if err := os.Unsetenv(auth.EnvReviewerKeys); err != nil {
		panic(err)
	}
	os.Exit(m.Run())
}
