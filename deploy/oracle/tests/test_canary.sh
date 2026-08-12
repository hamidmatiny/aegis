#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$ROOT_DIR/nginx-demo.conf.template"
CFG="$ROOT_DIR/canary-config.yml"

# Verify the template contains the exact-match locations we added.
grep -q "location = /.env.bak" "$TEMPLATE"
grep -q "location = /.git-credentials" "$TEMPLATE"

# Verify canary-config.yml lists the same paths.
grep -q "/.env.bak" "$CFG"
grep -q "/.git-credentials" "$CFG"

echo "canary checks OK"
