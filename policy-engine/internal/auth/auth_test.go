package auth_test

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aegis-platform/aegis/policy-engine/internal/auth"
)

func handlerOK() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
}

func TestMiddlewareRejectsMissingToken(t *testing.T) {
	h := auth.Middleware("secret-token")(handlerOK())
	req := httptest.NewRequest(http.MethodGet, "/v1/receipts", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 for missing token, got %d", rec.Code)
	}
}

func TestMiddlewareRejectsWrongToken(t *testing.T) {
	h := auth.Middleware("secret-token")(handlerOK())
	req := httptest.NewRequest(http.MethodGet, "/v1/receipts", nil)
	req.Header.Set("Authorization", "Bearer wrong-token")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 for wrong token, got %d", rec.Code)
	}
}

func TestMiddlewareAcceptsBearerToken(t *testing.T) {
	h := auth.Middleware("secret-token")(handlerOK())
	req := httptest.NewRequest(http.MethodGet, "/v1/receipts", nil)
	req.Header.Set("Authorization", "Bearer secret-token")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 for correct Bearer token, got %d", rec.Code)
	}
}

func TestMiddlewareAcceptsAlternateHeader(t *testing.T) {
	h := auth.Middleware("secret-token")(handlerOK())
	req := httptest.NewRequest(http.MethodGet, "/v1/receipts", nil)
	req.Header.Set("X-Aegis-Internal-Token", "secret-token")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 for correct X-Aegis-Internal-Token, got %d", rec.Code)
	}
}

func TestMiddlewareExemptsHealthAndReady(t *testing.T) {
	h := auth.Middleware("secret-token")(handlerOK())
	for _, path := range []string{"/health", "/ready"} {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("expected %s to be exempt (200), got %d", path, rec.Code)
		}
	}
}
