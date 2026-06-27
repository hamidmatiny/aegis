package api

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"

	"github.com/aegis-platform/aegis/model-router/internal/models"
	"github.com/aegis-platform/aegis/model-router/internal/provider"
	"github.com/aegis-platform/aegis/model-router/internal/router"
)

// Server exposes the model-router HTTP API.
type Server struct {
	router *router.Router
}

func NewServer(r *router.Router) *Server {
	return &Server{router: r}
}

func (s *Server) Register(mux *http.ServeMux) {
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/ready", s.handleReady)
	mux.HandleFunc("/v1/providers", s.handleListProviders)
	mux.HandleFunc("/v1/chat/completions", s.handleChatCompletions)
}

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "ok",
		"service": "model-router",
		"stage":   "4",
	})
}

func (s *Server) handleReady(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}

func (s *Server) handleListProviders(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"providers": s.router.ListProviders()})
}

func (s *Server) handleChatCompletions(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}

	var req models.ChatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if len(req.Messages) == 0 {
		writeError(w, http.StatusBadRequest, fmt.Errorf("messages required"))
		return
	}

	if req.Stream {
		s.handleStream(w, r, req)
		return
	}

	resp, err := s.router.Chat(r.Context(), req)
	if err != nil {
		writeRouterError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"id":       resp.ID,
		"object":   "chat.completion",
		"model":    resp.Model,
		"provider": resp.Provider,
		"choices": []map[string]any{{
			"index": 0,
			"message": map[string]string{
				"role":    "assistant",
				"content": resp.Content,
			},
			"finish_reason": resp.FinishReason,
		}},
		"usage": map[string]int{
			"prompt_tokens":     resp.Usage.PromptTokens,
			"completion_tokens": resp.Usage.CompletionTokens,
			"total_tokens":      resp.Usage.TotalTokens,
		},
		"aegis": map[string]any{
			"fallback_used":       resp.FallbackUsed,
			"attempted_providers": resp.AttemptedProviders,
		},
	})
}

func (s *Server) handleStream(w http.ResponseWriter, r *http.Request, req models.ChatRequest) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeError(w, http.StatusInternalServerError, fmt.Errorf("streaming not supported"))
		return
	}

	ch, providerID, err := s.router.ChatStream(r.Context(), req)
	if err != nil {
		writeRouterError(w, err)
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	for chunk := range ch {
		if chunk.Done {
			_, _ = fmt.Fprintf(w, "data: [DONE]\n\n")
			flusher.Flush()
			return
		}
		payload := map[string]any{
			"id":       chunk.ID,
			"object":   "chat.completion.chunk",
			"model":    chunk.Model,
			"provider": providerID,
			"choices": []map[string]any{{
				"index":         0,
				"delta":         map[string]string{"content": chunk.Delta},
				"finish_reason": chunk.FinishReason,
			}},
		}
		data, _ := json.Marshal(payload)
		_, _ = fmt.Fprintf(w, "data: %s\n\n", data)
		flusher.Flush()
	}
}

func writeRouterError(w http.ResponseWriter, err error) {
	if modelErr, ok := provider.AsModelRetiredError(err); ok {
		writeJSON(w, http.StatusUnprocessableEntity, map[string]any{
			"error": modelErr.Error(),
			"aegis": map[string]any{
				"model_error": map[string]any{
					"provider":       modelErr.Provider,
					"rejected_model": modelErr.RejectedModel,
					"error_type":     modelErr.ErrorType(),
					"message":        modelErr.Guidance(),
				},
			},
		})
		return
	}
	if authErr, ok := provider.AsAuthError(err); ok {
		writeJSON(w, http.StatusUnauthorized, map[string]any{
			"error": authErr.Error(),
			"aegis": map[string]any{
				"model_error": map[string]any{
					"provider":   authErr.Provider,
					"error_type": authErr.ErrorType(),
					"message":    authErr.Error(),
				},
			},
		})
		return
	}

	status := http.StatusBadGateway
	var routerErr *models.RouterError
	if errors.As(err, &routerErr) {
		status = http.StatusBadGateway
	}
	writeError(w, status, err)
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
	writeError(w, http.StatusMethodNotAllowed, fmt.Errorf("method not allowed"))
}
