#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$ROOT_DIR/nginx-demo.conf.template"
CFG="$ROOT_DIR/canary-config.yml"

# The template no longer hardcodes canary `location` blocks -- since Stage 2
# Phase 2 (commit f3faa84), those are generated from canary-config.yml by
# generate-canary-nginx.sh and spliced in at the ###CANARY_BLOCK### placeholder
# (see setup.sh). This test's job is now to guard the *source of truth*: that
# the placeholder is still present in the template, and that canary-config.yml
# still declares the two approved tokens. Whether the generator actually turns
# that config into correct nginx blocks is covered separately by
# test_canary_render.sh -- keep both, they check different failure modes.
grep -q "###CANARY_BLOCK###" "$TEMPLATE" || {
  echo "Template missing ###CANARY_BLOCK### placeholder -- canary generation is no longer wired in" >&2
  exit 1
}

grep -q "path: */\.env\.bak" "$CFG" || {
  echo "canary-config.yml missing the /.env.bak canary entry" >&2
  exit 1
}
grep -q "path: */\.git-credentials" "$CFG" || {
  echo "canary-config.yml missing the /.git-credentials canary entry" >&2
  exit 1
}

# Enforce the N31 safe-redirect rule at the config level: every target must be
# one of the allowlisted destinations (GitHub profile / repo / LinkedIn), never
# anything else -- no ads, no third-party URLs, no open redirect.
while IFS= read -r target; do
  case "$target" in
    https://github.com/hamidmatiny*|https://www.linkedin.com/in/*) ;;
    *)
      echo "canary-config.yml has a target outside the allowlist (GitHub/LinkedIn only): $target" >&2
      exit 1
      ;;
  esac
done < <(grep -oE 'target: *https://\S+' "$CFG" | sed 's/target: *//')

echo "canary checks OK"
