package main_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/aegis-platform/aegis/policy-engine/internal/api"
	"github.com/aegis-platform/aegis/policy-engine/internal/audit"
	"github.com/aegis-platform/aegis/policy-engine/internal/engine"
	"github.com/aegis-platform/aegis/policy-engine/internal/loader"
	"github.com/aegis-platform/aegis/policy-engine/internal/models"
)

func TestEvaluateInputHTTPEndpoint(t *testing.T) {
	dir := filepath.Join("..", "..", "policies")
	store, err := loader.NewStore(dir)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}
	srv := api.NewServer(store, engine.New(), audit.NewClient(""))
	mux := http.NewServeMux()
	srv.Register(mux)

	body, _ := json.Marshal(models.EvaluateInputRequest{
		TenantID: "default",
		Mode:     models.ModeEnforce,
		InputVerdict: models.InputVerdict{
			Action:     "BLOCK",
			FusedScore: 0.92,
			DetectorScores: []models.DetectorScore{
				{DetectorID: "heuristic", Score: 0.92, Reasoning: "test"},
			},
		},
	})
	req := httptest.NewRequest(http.MethodPost, "/v1/evaluate/input", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
	}
	var resp models.EvaluateResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatal(err)
	}
	if resp.Decision.Action != models.ActionBlock {
		t.Fatalf("expected block, got %s", resp.Decision.Action)
	}
}
