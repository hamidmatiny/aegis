package auth_test

import (
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"github.com/aegis-platform/aegis/gateway/internal/auth"
)

func TestLoad_GeneratesKeyWhenUnset(t *testing.T) {
	t.Setenv(auth.EnvKeys, "")
	cfg := auth.Load()
	if cfg.Source != auth.SourceGenerated {
		t.Fatalf("expected SourceGenerated, got %s", cfg.Source)
	}
	if cfg.GeneratedKey == "" || !cfg.Valid(cfg.GeneratedKey) {
		t.Fatalf("generated key should be valid, got %q", cfg.GeneratedKey)
	}
}

func TestLoad_UsesConfiguredKeys(t *testing.T) {
	t.Setenv(auth.EnvKeys, "key-one, key-two")
	cfg := auth.Load()
	if cfg.Source != auth.SourceConfigured {
		t.Fatalf("expected SourceConfigured, got %s", cfg.Source)
	}
	if !cfg.Valid("key-one") || !cfg.Valid("key-two") {
		t.Fatalf("configured keys should be valid")
	}
	if cfg.Valid("key-three") {
		t.Fatalf("unconfigured key should not be valid")
	}
}

func TestLoad_TwoCallsGenerateDifferentKeys(t *testing.T) {
	t.Setenv(auth.EnvKeys, "")
	a := auth.Load()
	b := auth.Load()
	if a.GeneratedKey == b.GeneratedKey {
		t.Fatalf("expected distinct generated keys across process restarts")
	}
}

func newTestMux() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	mux.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	mux.HandleFunc("/v1/chat/completions", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	return mux
}

func TestMiddleware_ExemptsHealthAndReady(t *testing.T) {
	cfg := auth.Config{Keys: map[string]struct{}{"secret": {}}, Source: auth.SourceConfigured}
	h := auth.Middleware(cfg)(newTestMux())

	for _, path := range []string{"/health", "/ready"} {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: expected 200 without a key, got %d", path, rec.Code)
		}
	}
}

func TestMiddleware_RejectsMissingKey(t *testing.T) {
	cfg := auth.Config{Keys: map[string]struct{}{"secret": {}}, Source: auth.SourceConfigured}
	h := auth.Middleware(cfg)(newTestMux())

	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 without a key, got %d", rec.Code)
	}
}

func TestMiddleware_RejectsWrongKey(t *testing.T) {
	cfg := auth.Config{Keys: map[string]struct{}{"secret": {}}, Source: auth.SourceConfigured}
	h := auth.Middleware(cfg)(newTestMux())

	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", nil)
	req.Header.Set("Authorization", "Bearer wrong-key")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 with a wrong key, got %d", rec.Code)
	}
}

func TestMiddleware_AcceptsBearerKey(t *testing.T) {
	cfg := auth.Config{Keys: map[string]struct{}{"secret": {}}, Source: auth.SourceConfigured}
	h := auth.Middleware(cfg)(newTestMux())

	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", nil)
	req.Header.Set("Authorization", "Bearer secret")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 with a valid bearer key, got %d", rec.Code)
	}
}

func TestMiddleware_AcceptsXAPIKeyHeader(t *testing.T) {
	cfg := auth.Config{Keys: map[string]struct{}{"secret": {}}, Source: auth.SourceConfigured}
	h := auth.Middleware(cfg)(newTestMux())

	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", nil)
	req.Header.Set("X-API-Key", "secret")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 with a valid X-API-Key header, got %d", rec.Code)
	}
}

func TestMain(m *testing.M) {
	// Ensure no ambient AEGIS_API_KEYS from the host leaks into tests.
	if err := os.Unsetenv(auth.EnvKeys); err != nil {
		panic(err)
	}
	os.Exit(m.Run())
}
