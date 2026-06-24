package router

import (
	"context"
	"fmt"
	"time"

	"github.com/aegis-platform/aegis/model-router/internal/config"
	"github.com/aegis-platform/aegis/model-router/internal/models"
	"github.com/aegis-platform/aegis/model-router/internal/provider"
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
	for id, entry := range r.cfg.Providers {
		p, ok := r.providers[id]
		healthy := false
		if ok {
			healthy = p.Ping(context.Background()) == nil
		}
		out = append(out, models.ProviderInfo{
			ID:      id,
			Enabled: entry.Enabled,
			BaseURL: entry.BaseURL,
			Healthy: healthy,
		})
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
