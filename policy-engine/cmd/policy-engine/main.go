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

	"github.com/aegis-platform/aegis/policy-engine/internal/api"
	"github.com/aegis-platform/aegis/policy-engine/internal/audit"
	"github.com/aegis-platform/aegis/policy-engine/internal/auth"
	"github.com/aegis-platform/aegis/policy-engine/internal/engine"
	"github.com/aegis-platform/aegis/policy-engine/internal/loader"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	port := envOr("AEGIS_POLICY_ENGINE_PORT", "8081")
	policyDir := envOr("AEGIS_POLICY_DIR", "policies")
	reloadSec := envInt("AEGIS_POLICY_RELOAD_SECONDS", 10)

	// policy-engine has no auth of its own beyond this shared internal
	// token — it was previously reachable, unauthenticated, by anything
	// that could reach it on the Docker network (including /v1/reload).
	// Unlike the gateway's AEGIS_API_KEYS, there is no ephemeral fallback
	// here: this token is shared by every internal service and the
	// handful of processes that call them, so a per-process generated
	// value would just desync from everyone else's copy and break every
	// internal call. Refuse to start instead of running open or broken.
	internalToken := os.Getenv(auth.EnvToken)
	if internalToken == "" {
		logger.Error(auth.EnvToken + " is not set — policy-engine refuses to start unauthenticated. " +
			"Run scripts/generate-credentials.sh, or set it explicitly (see .env.example).")
		os.Exit(1)
	}

	store, err := loader.NewStore(policyDir)
	if err != nil {
		logger.Error("failed to load policies", "error", err, "dir", policyDir)
		os.Exit(1)
	}

	eng := engine.New()
	auditClient := audit.NewClient(envOr("AEGIS_AUDIT_URL", ""), internalToken)
	srv := api.NewServer(store, eng, auditClient)

	mux := http.NewServeMux()
	srv.Register(mux)

	var handler http.Handler = mux
	handler = auth.Middleware(internalToken)(handler)

	httpServer := &http.Server{
		Addr:              ":" + port,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go watchPolicyReload(logger, store, reloadSec)

	go func() {
		logger.Info("policy-engine starting", "port", port, "policy_dir", policyDir, "audit_enabled", auditClient.Enabled())
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

func watchPolicyReload(logger *slog.Logger, store *loader.Store, intervalSec int) {
	if intervalSec <= 0 {
		return
	}
	ticker := time.NewTicker(time.Duration(intervalSec) * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		if err := store.Reload(); err != nil {
			logger.Warn("policy reload failed", "error", err)
		}
	}
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
