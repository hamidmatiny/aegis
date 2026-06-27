package router

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/aegis-platform/aegis/model-router/internal/config"
	"github.com/aegis-platform/aegis/model-router/internal/models"
	"github.com/aegis-platform/aegis/model-router/internal/provider"
)

const (
	modelStatusOK           = "ok"
	modelStatusInvalidModel = "invalid_model"
	modelStatusUnreachable  = "unreachable"
	modelStatusAuthFailed   = "auth_failed"
	modelStatusNotChecked   = "not_checked"
)

// Router selects providers, applies retry, and walks the fallback chain.
type Router struct {
	cfg       config.Config
	providers map[string]provider.Provider
}

func New(cfg config.Config, providers map[string]provider.Provider) *Router {
	return &Router{cfg: cfg, providers: providers}
}

func (r *Router) ListProviders() []models.ProviderInfo {
	out := make([]models.ProviderInfo, 0, len(r.cfg.Providers))
	ctx := context.Background()

	for id, entry := range r.cfg.Providers {
		info := models.ProviderInfo{
			ID:           id,
			Enabled:      entry.Enabled,
			BaseURL:      entry.BaseURL,
			DefaultModel: entry.DefaultModel,
			ModelStatus:  modelStatusNotChecked,
		}
		if entry.APIKeyEnv != "" {
			key := provider.ResolveAPIKey(provider.ProviderConfig{APIKeyEnv: entry.APIKeyEnv})
			info.APIKeyConfigured = key != ""
			info.APIKeyEnv = entry.APIKeyEnv
			info.APIKeyFingerprint = provider.APIKeyFingerprint(key)
		}

		if !entry.Enabled {
			info.Healthy = false
			info.ModelStatus = modelStatusNotChecked
			out = append(out, info)
			continue
		}

		p, ok := r.providers[id]
		if !ok {
			info.Healthy = false
			info.ModelStatus = modelStatusUnreachable
			out = append(out, info)
			continue
		}

		if id == "mock" {
			info.Healthy = true
			info.ModelStatus = modelStatusOK
			out = append(out, info)
			continue
		}

		pingErr := p.Ping(ctx)
		info.Healthy = pingErr == nil
		if pingErr != nil {
			info.ModelStatus = modelStatusUnreachable
			out = append(out, info)
			continue
		}

		if entry.DefaultModel == "" {
			info.ModelStatus = modelStatusNotChecked
			out = append(out, info)
			continue
		}

		if err := provider.CheckModel(ctx, p, entry.DefaultModel); err != nil {
			if modelErr, ok := provider.AsModelRetiredError(err); ok {
				info.ModelStatus = modelStatusInvalidModel
				info.ModelError = modelErrorDetail(modelErr)
				logModelRetired(modelErr)
			} else if authErr, ok := provider.AsAuthError(err); ok {
				info.ModelStatus = modelStatusAuthFailed
				info.ModelError = authErrorDetail(authErr)
				logAuthFailure(authErr)
			} else {
				info.ModelStatus = modelStatusUnreachable
			}
		} else {
			info.ModelStatus = modelStatusOK
		}

		out = append(out, info)
	}
	return out
}

func (r *Router) Chat(ctx context.Context, req models.ChatRequest) (*models.ChatResponse, error) {
	chain := r.cfg.ResolveChain(req.Provider, req.Model)
	var attempts []models.RouteAttempt

	for i, target := range chain {
		p, ok := r.providers[target.Provider]
		if !ok {
			attempts = append(attempts, models.RouteAttempt{
				Provider: target.Provider,
				Model:    target.Model,
				Err:      fmt.Errorf("provider not registered"),
			})
			continue
		}

		routed := req
		routed.Provider = target.Provider
		routed.Model = target.Model

		resp, err := r.tryWithRetry(ctx, p, routed)
		if err == nil {
			resp.FallbackUsed = i > 0
			resp.AttemptedProviders = attemptedIDs(attempts, target.Provider)
			return resp, nil
		}

		if modelErr, ok := provider.AsModelRetiredError(err); ok {
			logModelRetired(modelErr)
			return nil, modelErr
		}
		if authErr, ok := provider.AsAuthError(err); ok {
			logAuthFailure(authErr)
			return nil, authErr
		}

		attempts = append(attempts, models.RouteAttempt{
			Provider: target.Provider,
			Model:    target.Model,
			Err:      err,
		})
	}

	return nil, &models.RouterError{
		Message:  "all providers in fallback chain failed",
		Attempts: attempts,
	}
}

func (r *Router) ChatStream(ctx context.Context, req models.ChatRequest) (<-chan models.StreamChunk, string, error) {
	chain := r.cfg.ResolveChain(req.Provider, req.Model)
	var attempts []models.RouteAttempt

	for i, target := range chain {
		p, ok := r.providers[target.Provider]
		if !ok {
			attempts = append(attempts, models.RouteAttempt{
				Provider: target.Provider,
				Model:    target.Model,
				Err:      fmt.Errorf("provider not registered"),
			})
			continue
		}
		routed := req
		routed.Provider = target.Provider
		routed.Model = target.Model
		routed.Stream = true

		ch, err := p.ChatStream(ctx, routed)
		if err == nil {
			if i > 0 {
				ch = wrapFallbackNotice(ch, target.Provider)
			}
			return ch, target.Provider, nil
		}

		if modelErr, ok := provider.AsModelRetiredError(err); ok {
			logModelRetired(modelErr)
			return nil, "", modelErr
		}
		if authErr, ok := provider.AsAuthError(err); ok {
			logAuthFailure(authErr)
			return nil, "", authErr
		}

		attempts = append(attempts, models.RouteAttempt{
			Provider: target.Provider,
			Model:    target.Model,
			Err:      err,
		})
	}
	return nil, "", &models.RouterError{Message: "all providers in fallback chain failed", Attempts: attempts}
}

func (r *Router) tryWithRetry(ctx context.Context, p provider.Provider, req models.ChatRequest) (*models.ChatResponse, error) {
	var lastErr error
	for attempt := 1; attempt <= r.cfg.Retry.MaxAttempts; attempt++ {
		resp, err := p.Chat(ctx, req)
		if err == nil {
			return resp, nil
		}
		lastErr = err
		if provider.IsModelRetiredError(err) {
			return nil, err
		}
		if provider.IsAuthError(err) {
			return nil, err
		}
		if up, ok := err.(*provider.UpstreamError); ok && !up.Retryable() {
			return nil, err
		}
		if attempt < r.cfg.Retry.MaxAttempts {
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(time.Duration(r.cfg.Retry.BackoffMS) * time.Millisecond):
			}
		}
	}
	return nil, lastErr
}

func attemptedIDs(attempts []models.RouteAttempt, success string) []string {
	ids := make([]string, 0, len(attempts)+1)
	for _, a := range attempts {
		ids = append(ids, a.Provider)
	}
	ids = append(ids, success)
	return ids
}

func wrapFallbackNotice(ch <-chan models.StreamChunk, providerID string) <-chan models.StreamChunk {
	out := make(chan models.StreamChunk, 16)
	go func() {
		defer close(out)
		out <- models.StreamChunk{Delta: fmt.Sprintf("[fallback:%s] ", providerID), Provider: providerID}
		for chunk := range ch {
			out <- chunk
		}
	}()
	return out
}

func logModelRetired(err *provider.ModelRetiredError) {
	slog.Error(
		"configured model rejected by upstream — update providers.yaml with a current model ID",
		"provider", err.Provider,
		"rejected_model", err.RejectedModel,
		"status_code", err.StatusCode,
		"guidance", err.Guidance(),
		"upstream_body", err.UpstreamBody,
	)
}

func authErrorDetail(err *provider.AuthError) *models.ModelErrorDetail {
	return &models.ModelErrorDetail{
		Provider:  err.Provider,
		ErrorType: err.ErrorType(),
		Message:   err.Error(),
	}
}

func logAuthFailure(err *provider.AuthError) {
	slog.Error(
		"provider authentication failed — update runtime env (not image build)",
		"provider", err.Provider,
		"api_key_env", err.APIKeyEnv,
		"status_code", err.Status,
		"upstream_body", err.Body,
	)
}

func modelErrorDetail(err *provider.ModelRetiredError) *models.ModelErrorDetail {
	return &models.ModelErrorDetail{
		Provider:      err.Provider,
		RejectedModel: err.RejectedModel,
		ErrorType:     err.ErrorType(),
		Message:       err.Guidance(),
	}
}
