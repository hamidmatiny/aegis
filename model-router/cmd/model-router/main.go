package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/aegis-platform/aegis/model-router/internal/api"
	"github.com/aegis-platform/aegis/model-router/internal/config"
	"github.com/aegis-platform/aegis/model-router/internal/provider"
	"github.com/aegis-platform/aegis/model-router/internal/router"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	port := envOr("AEGIS_MODEL_ROUTER_PORT", "8082")
	cfgPath := config.ConfigPath()

	cfg, err := config.Load(cfgPath)
	if err != nil {
		logger.Error("failed to load config", "error", err, "path", cfgPath)
		os.Exit(1)
	}

	reg := provider.NewRegistry()
	providers, err := cfg.BuildRegistry(reg)
	if err != nil {
		logger.Error("failed to build providers", "error", err)
		os.Exit(1)
	}

	rtr := router.New(cfg, providers)
	srv := api.NewServer(rtr)

	mux := http.NewServeMux()
	srv.Register(mux)

	httpServer := &http.Server{
		Addr:              ":" + port,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		logger.Info("model-router starting",
			"port", port,
			"config", cfgPath,
			"default_provider", cfg.Routing.DefaultProvider,
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

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
