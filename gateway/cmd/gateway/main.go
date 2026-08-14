package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/aegis-platform/aegis/gateway/internal/api"
	"github.com/aegis-platform/aegis/gateway/internal/auth"
	"github.com/aegis-platform/aegis/gateway/internal/config"
	"github.com/aegis-platform/aegis/gateway/internal/pipeline"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	cfg := config.Load()
	authCfg := auth.Load()

	// input-defense, output-defense, and policy-engine all reject
	// unauthenticated requests now (see AEGIS_INTERNAL_TOKEN in
	// scripts/generate-credentials.sh). Refuse to start rather than run
	// with every internal call silently 401ing.
	if cfg.InternalToken == "" {
		logger.Error("AEGIS_INTERNAL_TOKEN is not set — gateway's calls to input-defense, output-defense, " +
			"and policy-engine will be rejected. Run scripts/generate-credentials.sh, or set it explicitly " +
			"(see .env.example).")
		os.Exit(1)
	}

	p := pipeline.New(cfg)
	srv := api.NewServer(p)

	mux := http.NewServeMux()
	srv.Register(mux)

	var handler http.Handler = mux
	handler = auth.Middleware(authCfg)(handler)

	httpServer := &http.Server{
		Addr:              ":" + cfg.HTTPPort,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		logger.Info("gateway starting",
			"port", cfg.HTTPPort,
			"input_defense", cfg.InputDefenseURL,
			"output_defense", cfg.OutputDefenseURL,
			"policy_engine", cfg.PolicyEngineURL,
			"model_router", cfg.ModelRouterURL,
			"agent_gate", cfg.AgentGateURL,
		)
		switch authCfg.Source {
		case auth.SourceGenerated:
			logger.Warn("AEGIS_API_KEYS not set — generated a one-time API key for this process. "+
				"It will change on restart. Set AEGIS_API_KEYS in your environment (see scripts/generate-credentials.sh) "+
				"to persist a key across restarts.",
				"generated_api_key", authCfg.GeneratedKey)
		case auth.SourceConfigured:
			logger.Info("gateway API key auth enabled", "configured_key_count", len(authCfg.Keys))
		}
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("server failed", "error", err)
			os.Exit(1)
		}
	}()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = httpServer.Shutdown(ctx)
}
