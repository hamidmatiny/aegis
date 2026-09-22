package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/aegis-platform/aegis/audit/internal/models"
	"github.com/aegis-platform/aegis/audit/internal/service"
	"github.com/aegis-platform/aegis/audit/internal/store"
)

type Server struct {
	svc     *service.Service
	keysURI string // optional advertisement for export metadata (X-Aegis-Keys-Uri)
}

func NewServer(svc *service.Service) *Server {
	return &Server{svc: svc}
}

// WithKeysURI sets the optional export-metadata hint for JWKS discovery
// (header X-Aegis-Keys-Uri). Not embedded in signed receipts.
func (s *Server) WithKeysURI(uri string) *Server {
	s.keysURI = uri
	return s
}

func (s *Server) Register(mux *http.ServeMux) {
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/ready", s.handleReady)
	mux.HandleFunc("/v1/receipts", s.handleReceipts)
	mux.HandleFunc("/v1/receipts/", s.handleReceiptByID)
	mux.HandleFunc("/v1/export", s.handleExport)
	mux.HandleFunc("/v1/keys", s.handleKeys)
	mux.HandleFunc("/v1/keys/", s.handleKeyByID)
	mux.HandleFunc("/.well-known/jwks.json", s.handleJWKS)
}

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "ok",
		"service": "audit",
		"stage":   "8",
	})
}

func (s *Server) handleReady(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}

func (s *Server) handleReceipts(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodPost:
		var req models.WriteReceiptRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeError(w, http.StatusBadRequest, err)
			return
		}
		resp, err := s.svc.Write(r.Context(), req)
		if err != nil {
			writeError(w, http.StatusBadRequest, err)
			return
		}
		writeJSON(w, http.StatusCreated, resp)
	case http.MethodGet:
		query, err := parseQuery(r)
		if err != nil {
			writeError(w, http.StatusBadRequest, err)
			return
		}
		resp, err := s.svc.Query(r.Context(), query)
		if err != nil {
			writeError(w, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, resp)
	default:
		methodNotAllowed(w)
	}
}

func (s *Server) handleReceiptByID(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/v1/receipts/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) == 0 || parts[0] == "" {
		writeError(w, http.StatusNotFound, errors.New("receipt id required"))
		return
	}
	receiptID := parts[0]

	if len(parts) == 2 && parts[1] == "verify" && r.Method == http.MethodGet {
		resp, err := s.svc.Verify(r.Context(), receiptID)
		if err != nil {
			if errors.Is(err, store.ErrNotFound) {
				writeError(w, http.StatusNotFound, err)
				return
			}
			writeError(w, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, resp)
		return
	}

	if len(parts) == 1 && r.Method == http.MethodGet {
		receipt, err := s.svc.Get(r.Context(), receiptID)
		if err != nil {
			if errors.Is(err, store.ErrNotFound) {
				writeError(w, http.StatusNotFound, err)
				return
			}
			writeError(w, http.StatusInternalServerError, err)
			return
		}
		writeJSON(w, http.StatusOK, receipt)
		return
	}

	methodNotAllowed(w)
}

func (s *Server) handleExport(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	var req models.ExportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	data, contentType, filename, err := s.svc.Export(r.Context(), req)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Content-Disposition", "attachment; filename="+filename)
	if s.keysURI != "" {
		w.Header().Set("X-Aegis-Keys-Uri", s.keysURI)
	}
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(data)
}

func (s *Server) handleKeys(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	s.writeJWKS(w)
}

func (s *Server) handleJWKS(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	s.writeJWKS(w)
}

func (s *Server) handleKeyByID(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	kid := strings.Trim(strings.TrimPrefix(r.URL.Path, "/v1/keys/"), "/")
	if kid == "" || strings.Contains(kid, "/") {
		writeError(w, http.StatusNotFound, errors.New("key id required"))
		return
	}
	jwk, ok := s.svc.JWK(kid)
	if !ok {
		writeError(w, http.StatusNotFound, errors.New("unknown signing key id"))
		return
	}
	w.Header().Set("Cache-Control", "public, max-age=300")
	writeJSON(w, http.StatusOK, jwk)
}

func (s *Server) writeJWKS(w http.ResponseWriter) {
	w.Header().Set("Cache-Control", "public, max-age=300")
	writeJSON(w, http.StatusOK, s.svc.JWKS())
}

func parseQuery(r *http.Request) (models.QueryRequest, error) {
	q := r.URL.Query()
	req := models.QueryRequest{
		TenantID:  q.Get("tenant_id"),
		EventType: q.Get("event_type"),
		TraceID:   q.Get("trace_id"),
		Cursor:    q.Get("cursor"),
	}
	if limitStr := q.Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err != nil {
			return req, err
		}
		req.Limit = limit
	}
	if start := q.Get("start_time"); start != "" {
		t, err := time.Parse(time.RFC3339, start)
		if err != nil {
			return req, err
		}
		req.StartTime = &t
	}
	if end := q.Get("end_time"); end != "" {
		t, err := time.Parse(time.RFC3339, end)
		if err != nil {
			return req, err
		}
		req.EndTime = &t
	}
	return req, nil
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
