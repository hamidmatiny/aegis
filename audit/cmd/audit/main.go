package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/aegis-platform/aegis/audit/internal/api"
	"github.com/aegis-platform/aegis/audit/internal/service"
	"github.com/aegis-platform/aegis/audit/internal/signer"
	"github.com/aegis-platform/aegis/audit/internal/store"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	port := envOr("AEGIS_AUDIT_PORT", "8084")
	databaseURL := os.Getenv("DATABASE_URL")
	keyID := envOr("AEGIS_AUDIT_SIGNING_KEY_ID", "dev-key-1")
	keyMaterial := os.Getenv("AEGIS_AUDIT_SIGNING_KEY")

	var sg *signer.Signer
	var err error
	if keyMaterial == "" {
		logger.Warn("AEGIS_AUDIT_SIGNING_KEY not set; generating ephemeral dev key")
		sg, err = signer.GenerateDev(keyID)
	} else {
		sg, err = signer.New(keyID, keyMaterial)
	}
	if err != nil {
		logger.Error("failed to initialize signer", "error", err)
		os.Exit(1)
	}

	var st store.Store
	var pgStore *store.PostgresStore
	if databaseURL != "" {
		pgStore, err = store.NewPostgresStore(databaseURL)
		if err != nil {
			logger.Error("postgres unavailable", "error", err)
			os.Exit(1)
		}
		st = pgStore
		logger.Info("audit store", "backend", "postgres")
	} else {
		st = store.NewMemoryStore()
		logger.Warn("DATABASE_URL not set; using in-memory store")
	}

	svc := service.New(st, sg)
	mux := http.NewServeMux()
	api.NewServer(svc).Register(mux)

	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		logger.Info("audit starting", "port", port, "signer_key_id", sg.KeyID())
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
	if pgStore != nil {
		_ = pgStore.Close()
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
