package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"github.com/aegis-platform/aegis/agent-gate/internal/audit"
	"github.com/aegis-platform/aegis/agent-gate/internal/gate"
	"github.com/aegis-platform/aegis/agent-gate/internal/models"
)

// Server exposes the agent-gate HTTP API.
type Server struct {
	gate  *gate.Gate
	audit *audit.Client
}

func NewServer(g *gate.Gate, auditClient *audit.Client) *Server {
	return &Server{gate: g, audit: auditClient}
}

func (s *Server) Register(mux *http.ServeMux) {
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/ready", s.handleReady)
	mux.HandleFunc("/v1/evaluate", s.handleEvaluate)
	mux.HandleFunc("/v1/approvals/", s.handleApprovals)
}

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "ok",
		"service": "agent-gate",
		"stage":   "6",
	})
}

func (s *Server) handleReady(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}

func (s *Server) handleEvaluate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var req models.EvaluateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if req.ToolCall.ToolName == "" {
		writeError(w, http.StatusBadRequest, errors.New("tool_call.tool_name required"))
		return
	}
	if req.TenantID == "" {
		req.TenantID = "default"
	}

	resp, err := s.gate.Evaluate(r.Context(), req)
	if err != nil {
		writeError(w, http.StatusBadGateway, err)
		return
	}
	if s.audit != nil {
		s.audit.EmitToolGate(req.TenantID, audit.TraceFromRequest(req), resp.Decision, resp.PolicyAction)
	}
	writeJSON(w, http.StatusOK, resp)
}

func (s *Server) handleApprovals(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/v1/approvals/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) == 0 || parts[0] == "" {
		writeError(w, http.StatusNotFound, errors.New("approval id required"))
		return
	}
	approvalID := parts[0]

	if len(parts) == 1 && r.Method == http.MethodGet {
		appr, err := s.gate.GetApproval(r.Context(), approvalID)
		if err != nil {
			writeError(w, http.StatusNotFound, err)
			return
		}
		writeJSON(w, http.StatusOK, appr)
		return
	}

	if len(parts) == 2 && parts[1] == "decide" && r.Method == http.MethodPost {
		var action models.ApprovalAction
		if err := json.NewDecoder(r.Body).Decode(&action); err != nil {
			writeError(w, http.StatusBadRequest, err)
			return
		}
		action.ApprovalID = approvalID
		decision, err := s.gate.SubmitApproval(r.Context(), action)
		if err != nil {
			writeError(w, http.StatusBadRequest, err)
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"decision": decision})
		return
	}

	methodNotAllowed(w)
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
