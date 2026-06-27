package main_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/aegis-platform/aegis/gateway/internal/api"
	"github.com/aegis-platform/aegis/gateway/internal/config"
	"github.com/aegis-platform/aegis/gateway/internal/pipeline"
)

func TestHealthHandler(t *testing.T) {
	srv := api.NewServer(pipeline.New(config.Config{}))
	mux := http.NewServeMux()
	srv.Register(mux)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["service"] != "aegis-gateway" || body["stage"] != "H4" {
		t.Fatalf("unexpected health body: %#v", body)
	}
}
