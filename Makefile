.PHONY: all proto lint test test-go test-python test-integration \
        docker-up docker-down docker-build bench clean

all: proto lint test

# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------
proto:
	@command -v buf >/dev/null 2>&1 || { echo "buf not installed; see https://buf.build/docs/installation"; exit 1; }
	cd shared && buf lint && buf generate

proto-lint:
	cd shared && buf lint

# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------
lint: lint-go lint-python lint-ts

lint-go:
	@for dir in gateway policy-engine model-router agent-gate audit; do \
		if [ -f "$$dir/go.mod" ]; then \
			echo "==> golangci-lint $$dir"; \
			(cd "$$dir" && GOWORK=off golangci-lint run ./...) || exit 1; \
		fi; \
	done

lint-python:
	@for dir in input-defense output-defense redteam sdk/python; do \
		if [ -f "$$dir/pyproject.toml" ]; then \
			echo "==> ruff $$dir"; \
			(cd "$$dir" && ruff check . && ruff format --check .) || exit 1; \
			echo "==> mypy $$dir"; \
			(cd "$$dir" && mypy src) || exit 1; \
		fi; \
	done

lint-ts:
	@if [ -f dashboard/package.json ]; then \
		cd dashboard && npm run lint; \
	fi
	@if [ -f sdk/typescript/package.json ]; then \
		cd sdk/typescript && npm run lint; \
	fi

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
test: test-go test-python

test-go:
	@for dir in gateway policy-engine model-router agent-gate audit; do \
		if [ -f "$$dir/go.mod" ]; then \
			echo "==> go test $$dir"; \
			(cd "$$dir" && GOWORK=off go test ./...) || exit 1; \
		fi; \
	done

test-python:
	@for dir in input-defense output-defense redteam sdk/python; do \
		if [ -f "$$dir/pyproject.toml" ]; then \
			echo "==> pytest $$dir"; \
			(cd "$$dir" && pytest) || exit 1; \
		fi; \
	done

test-integration:
	./scripts/integration

bench:
	./scripts/benchmark.sh

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v

docker-build:
	docker compose build

docker-logs:
	docker compose logs -f

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
clean:
	rm -rf shared/gen/go shared/gen/python
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

dev-setup:
	./scripts/dev-setup.sh
