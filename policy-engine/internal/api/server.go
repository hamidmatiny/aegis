package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"github.com/aegis-platform/aegis/policy-engine/internal/audit"
	"github.com/aegis-platform/aegis/policy-engine/internal/engine"
	"github.com/aegis-platform/aegis/policy-engine/internal/loader"
	"github.com/aegis-platform/aegis/policy-engine/internal/models"
)

// Server exposes the policy engine HTTP API.
type Server struct {
	store  *loader.Store
	engine *engine.Engine
	audit  *audit.Client
}

func NewServer(store *loader.Store, eng *engine.Engine, auditClient *audit.Client) *Server {
	return &Server{store: store, engine: eng, audit: auditClient}
}

func (s *Server) Register(mux *http.ServeMux) {
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/ready", s.handleReady)
	mux.HandleFunc("/v1/policy-packs", s.handlePolicyPacks)
	mux.HandleFunc("/v1/policy-packs/", s.handlePolicyPackByID)
	mux.HandleFunc("/v1/dry-run", s.handleDryRun)
	mux.HandleFunc("/v1/evaluate/input", s.handleEvaluateInput)
	mux.HandleFunc("/v1/evaluate/output", s.handleEvaluateOutput)
	mux.HandleFunc("/v1/evaluate/tool", s.handleEvaluateTool)
	mux.HandleFunc("/v1/reload", s.handleReload)
}

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "ok",
		"service": "policy-engine",
		"stage":   "3",
	})
}

func (s *Server) handleReady(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}

func (s *Server) handlePolicyPacks(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/v1/policy-packs" {
		http.NotFound(w, r)
		return
	}
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"policy_packs": s.store.ListBasePacks(),
	})
}

func (s *Server) handlePolicyPackByID(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	packID := strings.TrimPrefix(r.URL.Path, "/v1/policy-packs/")
	packID = strings.Trim(packID, "/")
	if packID == "" {
		writeError(w, http.StatusNotFound, errors.New("policy pack id required"))
		return
	}
	pack, err := s.store.Resolve("default", packID)
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	sourceYAML, err := s.store.ReadPackYAML(packID)
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"pack":        pack,
		"source_yaml": sourceYAML,
	})
}

func (s *Server) handleDryRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var req models.DryRunRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if req.YAML == "" {
		writeError(w, http.StatusBadRequest, errors.New("yaml is required"))
		return
	}
	pack, err := loader.ParsePackYAML(req.YAML)
	if err != nil {
		writeJSON(w, http.StatusOK, models.DryRunResponse{Valid: false, Error: err.Error()})
		return
	}
	tenantID := req.TenantID
	if tenantID == "" {
		tenantID = "default"
	}

	var decision models.PolicyDecision
	switch req.RuleSet {
	case "input", "":
		var verdict models.InputVerdict
		if len(req.Sample) > 0 {
			if err := json.Unmarshal(req.Sample, &verdict); err != nil {
				writeJSON(w, http.StatusOK, models.DryRunResponse{Valid: false, Error: "invalid input sample: " + err.Error()})
				return
			}
		} else {
			verdict = models.InputVerdict{Action: "BLOCK", FusedScore: 0.9}
		}
		decision, err = s.engine.EvaluateInput(pack, tenantID, verdict, models.ModeDryRun)
	case "output":
		var verdict models.OutputVerdict
		if len(req.Sample) > 0 {
			if err := json.Unmarshal(req.Sample, &verdict); err != nil {
				writeJSON(w, http.StatusOK, models.DryRunResponse{Valid: false, Error: "invalid output sample: " + err.Error()})
				return
			}
		} else {
			verdict = models.OutputVerdict{Action: "BLOCK", FusedScore: 0.85}
		}
		decision, err = s.engine.EvaluateOutput(pack, tenantID, verdict, models.ModeDryRun)
	case "tool":
		var toolCall models.ToolCallRequest
		if len(req.Sample) > 0 {
			if err := json.Unmarshal(req.Sample, &toolCall); err != nil {
				writeJSON(w, http.StatusOK, models.DryRunResponse{Valid: false, Error: "invalid tool sample: " + err.Error()})
				return
			}
		} else {
			toolCall = models.ToolCallRequest{ToolName: "delete_file", RiskLevel: "IRREVERSIBLE"}
		}
		decision, err = s.engine.EvaluateTool(pack, tenantID, toolCall, models.ModeDryRun)
	default:
		writeJSON(w, http.StatusOK, models.DryRunResponse{Valid: false, Error: "rule_set must be input, output, or tool"})
		return
	}
	if err != nil {
		writeJSON(w, http.StatusOK, models.DryRunResponse{Valid: false, Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, models.DryRunResponse{Valid: true, Decision: &decision})
}

func (s *Server) handleReload(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	if err := s.store.Reload(); err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "reloaded"})
}

func (s *Server) handleEvaluateInput(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var req models.EvaluateInputRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	pack, err := s.store.Resolve(req.TenantID, req.PolicyPackID)
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	mode := normalizeMode(req.Mode, pack.Settings.ShadowMode)
	decision, err := s.engine.EvaluateInput(pack, req.TenantID, req.InputVerdict, mode)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if s.audit != nil {
		s.audit.EmitPolicyDecision(req.TenantID, req.Trace, decision)
	}
	writeJSON(w, http.StatusOK, models.EvaluateResponse{Decision: decision})
}

func (s *Server) handleEvaluateOutput(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var req models.EvaluateOutputRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	pack, err := s.store.Resolve(req.TenantID, req.PolicyPackID)
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	mode := normalizeMode(req.Mode, pack.Settings.ShadowMode)
	decision, err := s.engine.EvaluateOutput(pack, req.TenantID, req.OutputVerdict, mode)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if s.audit != nil {
		s.audit.EmitPolicyDecision(req.TenantID, req.Trace, decision)
	}
	writeJSON(w, http.StatusOK, models.EvaluateResponse{Decision: decision})
}

func (s *Server) handleEvaluateTool(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var req models.EvaluateToolRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	pack, err := s.store.Resolve(req.TenantID, req.PolicyPackID)
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	mode := normalizeMode(req.Mode, pack.Settings.ShadowMode)
	decision, err := s.engine.EvaluateTool(pack, req.TenantID, req.ToolCall, mode)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	writeJSON(w, http.StatusOK, models.EvaluateResponse{Decision: decision})
}

func normalizeMode(requestMode models.EvaluationMode, packShadow bool) models.EvaluationMode {
	if requestMode != "" {
		return requestMode
	}
	if packShadow {
		return models.ModeShadow
	}
	return models.ModeEnforce
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, err error) {
	writeJSON(w, status, map[string]string{"error": err.Error()})
}

func methodNotAllowed(w http.ResponseWriter) {
	writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"))
}
