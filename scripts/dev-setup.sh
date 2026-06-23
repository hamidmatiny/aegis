#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> AEGIS dev environment setup"

# Go tools
if command -v go >/dev/null 2>&1; then
  go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
fi

# Buf (protobuf)
if ! command -v buf >/dev/null 2>&1; then
  echo "Install buf: https://buf.build/docs/installation"
fi

# Python venvs for detector services
for svc in input-defense output-defense redteam; do
  if [ -f "$ROOT/$svc/pyproject.toml" ]; then
    echo "==> Setting up Python venv for $svc"
    (cd "$ROOT/$svc" && python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]')
  fi
done

# Generate protobuf code
if command -v buf >/dev/null 2>&1; then
  make -C "$ROOT" proto
fi

echo "==> Done. Copy .env.example to .env and run: make docker-up"
