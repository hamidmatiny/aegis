package auth_test

import (
	"net/http"
	"net/http/httptest"
	"os"
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

func TestMain(m *testing.M) {
	if err := os.Unsetenv(auth.EnvServiceKeys); err != nil {
		panic(err)
	}
	if err := os.Unsetenv(auth.EnvReviewerKeys); err != nil {
		panic(err)
	}
	os.Exit(m.Run())
}
