#!/usr/bin/env bash
# E2E: dashboard UI + proxied backend APIs
set -euo pipefail

DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:3000}"

echo "==> E2E: AEGIS dashboard"
echo "    dashboard: $DASHBOARD_URL"

curl -sf "$DASHBOARD_URL/" >/dev/null || { echo "FAIL: dashboard unreachable"; exit 1; }

echo ""
echo "-- Proxied audit health --"
curl -sf "$DASHBOARD_URL/api/audit/health" | grep -q '"service":"audit"' || {
  echo "FAIL: audit proxy"
  exit 1
}

echo "-- Proxied policy pack detail --"
curl -sf "$DASHBOARD_URL/api/policy/v1/policy-packs/default" | grep -q '"source_yaml"' || {
  echo "FAIL: policy pack proxy"
  exit 1
}

echo "-- Proxied approvals list --"
curl -sf "$DASHBOARD_URL/api/agent-gate/v1/approvals" | grep -q '"approvals"' || {
  echo "FAIL: approvals proxy"
  exit 1
}

echo "-- Proxied redteam campaigns --"
curl -sf "$DASHBOARD_URL/api/redteam/v1/campaigns" | grep -q '"campaigns"' || {
  echo "FAIL: campaigns proxy"
  exit 1
}

echo ""
echo "PASS: dashboard E2E"
