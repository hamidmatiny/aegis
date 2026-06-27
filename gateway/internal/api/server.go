package api

import (
	"encoding/json"
	"errors"
	"net/http"

	"github.com/aegis-platform/aegis/gateway/internal/pipeline"
)

// Server exposes the gateway HTTP API (OpenAI-compatible + tool evaluation).
type Server struct {
	pipeline *pipeline.Pipeline
}

func NewServer(p *pipeline.Pipeline) *Server {
	return &Server{pipeline: p}
}

func (s *Server) Register(mux *http.ServeMux) {
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/ready", s.handleReady)
	mux.HandleFunc("/v1/chat/completions", s.handleChatCompletions)
	mux.HandleFunc("/v1/tools/evaluate", s.handleEvaluateTool)
}

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "ok",
		"service": "aegis-gateway",
		"stage":   "H4",
	})
}

func (s *Server) handleReady(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}

func (s *Server) handleChatCompletions(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var req pipeline.ChatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}

	result, err := s.pipeline.ChatCompletions(r.Context(), req, nil)
	if err != nil {
		writePipelineError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func (s *Server) handleEvaluateTool(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var req pipeline.ToolEvaluateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	result, err := s.pipeline.EvaluateTool(r.Context(), req.ToolCall, nil)
	if err != nil {
		writePipelineError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func writePipelineError(w http.ResponseWriter, err error) {
	var blocked *pipeline.PolicyBlockedError
	if errors.As(err, &blocked) {
		writeJSON(w, http.StatusForbidden, map[string]any{
			"error": map[string]any{
				"type":          "aegis_policy_blocked",
				"message":       blocked.Message,
				"layer":         blocked.Layer,
				"policy_action": blocked.PolicyAction,
				"action":        blocked.Action,
				"fused_score":   blocked.FusedScore,
			},
		})
		return
	}
	var approval *pipeline.ApprovalRequiredError
	if errors.As(err, &approval) {
		writeJSON(w, http.StatusForbidden, map[string]any{
			"error": map[string]any{
				"type":         "aegis_approval_required",
				"message":      approval.Message,
				"approval_id":  approval.ApprovalID,
				"tool_name":    approval.ToolName,
			},
		})
		return
	}
	var provider *pipeline.ProviderError
	if errors.As(err, &provider) {
		status := provider.StatusCode
		if status == 0 {
			status = http.StatusBadGateway
		}
		writeJSON(w, status, map[string]any{
			"error": map[string]any{
				"type":     provider.ErrorType,
				"message":  provider.Message,
				"provider": provider.Provider,
				"model":    provider.Model,
			},
			"aegis": provider.Details,
		})
		return
	}
	var streaming *pipeline.StreamingUnsupportedError
	if errors.As(err, &streaming) {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"error": map[string]any{
				"type":    streaming.ErrorType(),
				"message": streaming.Error(),
			},
		})
		return
	}
	writeError(w, http.StatusBadGateway, err)
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
