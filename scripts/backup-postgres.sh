#!/usr/bin/env bash
# Backs up the aegis Postgres database (audit_receipts -- the signed audit
# trail -- and attack_patterns -- the redteam's learned adaptive-attack
# corpus; postgres_data is the ONLY persistent docker volume in this stack,
# see DR-RUNBOOK.md) to a single encrypted snapshot.
#
# Deliberately a single overwritten "latest" file, not a growing history --
# right for this project's actual scale (a solo-operated demo box, not a
# service with a real point-in-time-recovery requirement). Reuses Stage
# B.1's existing SOPS+age setup (.sops.yaml) rather than inventing a
# second secrets/backup mechanism -- same age recipient, a new binary-mode
# creation rule alongside the existing dotenv one for .env.
#
# Meant to run daily via cron (deploy/oracle/setup.sh wires this up
# automatically on the Oracle box) but works anywhere docker compose and
# the stack are available -- run it manually any time with:
#   ./scripts/backup-postgres.sh
#
# This backs up postgres_data to a file ON THIS BOX. It does NOT protect
# against losing the whole box -- see DR-RUNBOOK.md for why that's a
# deliberate, disclosed choice (not automated here) and what to do about it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

BACKUP_DIR="$ROOT/backups"
mkdir -p "$BACKUP_DIR"
PLAIN_FILE="$BACKUP_DIR/postgres-latest.sql.gz"
ENC_FILE="$BACKUP_DIR/postgres-latest.sql.gz.enc"

if [[ -f "$ROOT/.env" && ( -z "${POSTGRES_USER:-}" || -z "${POSTGRES_DB:-}" ) ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
POSTGRES_USER="${POSTGRES_USER:-aegis}"
POSTGRES_DB="${POSTGRES_DB:-aegis}"

if [[ -z "$($COMPOSE ps postgres --status running -q 2>/dev/null)" ]]; then
  echo "error: the postgres service isn't running (checked via docker compose ps)." >&2
  echo "       Start the stack first: docker compose up -d" >&2
  exit 1
fi

echo "==> Dumping ${POSTGRES_DB} (as ${POSTGRES_USER}) ..."
if ! $COMPOSE exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$PLAIN_FILE.tmp"; then
  echo "error: pg_dump failed -- see output above. $PLAIN_FILE was not updated." >&2
  rm -f "$PLAIN_FILE.tmp"
  exit 1
fi
mv "$PLAIN_FILE.tmp" "$PLAIN_FILE"
echo "==> Wrote $PLAIN_FILE ($(du -h "$PLAIN_FILE" | cut -f1))"

# Same gate as generate-credentials.sh's .env.enc step: only attempt
# encryption if sops/age are installed and .sops.yaml has a real
# recipient configured, not the placeholder. Silent, safe no-op otherwise
# -- the plain dump above still exists locally either way.
if command -v sops >/dev/null 2>&1 && command -v age >/dev/null 2>&1 \
   && [ -f "$ROOT/.sops.yaml" ] \
   && ! grep -q "REPLACE_WITH_YOUR_AGE_PUBLIC_KEY" "$ROOT/.sops.yaml"; then
  echo "==> Encrypting backup ($ENC_FILE)..."
  if sops --input-type binary --output-type binary --encrypt "$PLAIN_FILE" > "$ENC_FILE.tmp" 2>/tmp/sops-backup-encrypt.err; then
    mv "$ENC_FILE.tmp" "$ENC_FILE"
    echo "    $ENC_FILE updated. It's safe to commit (ciphertext) if you want an"
    echo "    off-box copy in git -- see DR-RUNBOOK.md for why that's a manual,"
    echo "    deliberate step here rather than something this script does for you."
  else
    echo "WARNING: sops encryption failed, $ENC_FILE NOT updated:" >&2
    cat /tmp/sops-backup-encrypt.err >&2
  fi
  rm -f "$ENC_FILE.tmp" /tmp/sops-backup-encrypt.err
else
  echo "==> Skipping encrypted backup (sops/age not installed, or .sops.yaml"
  echo "    still has its placeholder key) -- see .sops.yaml to set this up."
  echo "    $PLAIN_FILE (unencrypted) is still up to date."
fi

echo "==> Backup complete."
