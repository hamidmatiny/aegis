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
	"github.com/aegis-platform/aegis/gateway/internal/config"
	"github.com/aegis-platform/aegis/gateway/internal/pipeline"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	cfg := config.Load()
	p := pipeline.New(cfg)
	srv := api.NewServer(p)

	mux := http.NewServeMux()
	srv.Register(mux)

	httpServer := &http.Server{
		Addr:              ":" + cfg.HTTPPort,
		Handler:           mux,
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
