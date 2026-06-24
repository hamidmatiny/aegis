package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/aegis-platform/aegis/agent-gate/internal/api"
	"github.com/aegis-platform/aegis/agent-gate/internal/approval"
	"github.com/aegis-platform/aegis/agent-gate/internal/gate"
	"github.com/aegis-platform/aegis/agent-gate/internal/policy"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	port := envOr("AEGIS_AGENT_GATE_PORT", "8083")
	policyURL := envOr("AEGIS_POLICY_ENGINE_URL", "http://localhost:8081")
	approvalTTLHours := envInt("AEGIS_APPROVAL_TTL_HOURS", 24)

	policyClient := policy.NewClient(policyURL)
	approvalStore := approval.NewStore(time.Duration(approvalTTLHours) * time.Hour)
	g := gate.New(policyClient, approvalStore)

	mux := http.NewServeMux()
	api.NewServer(g).Register(mux)

	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		logger.Info("agent-gate starting",
			"port", port,
			"policy_engine_url", policyURL,
		)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("server failed", "error", err)
			os.Exit(1)
		}
	}()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = srv.Shutdown(ctx)
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		var n int
		if _, err := fmt.Sscanf(v, "%d", &n); err == nil {
			return n
		}
	}
	return fallback
}
