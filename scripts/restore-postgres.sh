#!/usr/bin/env bash
# Restores the aegis Postgres database from an encrypted backup produced by
# scripts/backup-postgres.sh. Use this when:
#   - setting up a NEW box and restoring postgres_data from an off-box copy
#     of the encrypted dump (see DR-RUNBOOK.md -- that off-box copy is a
#     manual step, not something any script does automatically)
#   - the live database was corrupted or accidentally wiped and needs to be
#     restored from the last local backup
#
# Requires the same age private key as scripts/decrypt-credentials.sh
# (SOPS_AGE_KEY_FILE, or the default ~/.config/sops/age/keys.txt).
#
# Refuses to restore into a database that already has audit_receipts rows
# unless given --force, since pg_dump's plain-SQL INSERTs will collide with
# any already-present rows sharing the same primary key -- same
# don't-clobber-without-being-asked posture as decrypt-credentials.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

ENC_FILE="$ROOT/backups/postgres-latest.sql.gz.enc"
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      ENC_FILE="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    *)
      echo "usage: $0 [--file path/to/backup.sql.gz.enc] [--force]" >&2
      exit 1
      ;;
  esac
done

if ! command -v sops >/dev/null 2>&1; then
  echo "error: sops is not installed. See .sops.yaml for setup." >&2
  exit 1
fi
if ! command -v age >/dev/null 2>&1; then
  echo "error: age is not installed. See .sops.yaml for setup." >&2
  exit 1
fi
if [ ! -f "$ENC_FILE" ]; then
  echo "error: $ENC_FILE not found -- nothing to restore." >&2
  echo "       Pass --file to point at a different backup, or run" >&2
  echo "       scripts/backup-postgres.sh first if you meant to restore" >&2
  echo "       from this box's own most recent backup." >&2
  exit 1
fi
if [ -z "${SOPS_AGE_KEY_FILE:-}" ] && [ ! -f "$HOME/.config/sops/age/keys.txt" ]; then
  echo "error: no age private key found. Set SOPS_AGE_KEY_FILE to point at it," >&2
  echo "       e.g.:" >&2
  echo "         export SOPS_AGE_KEY_FILE=/path/to/age-key.txt" >&2
  echo "         ./scripts/restore-postgres.sh" >&2
  exit 1
fi

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

EXISTING_ROWS="$($COMPOSE exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT count(*) FROM audit_receipts" 2>/dev/null | tr -d '[:space:]' || echo "")"

if [[ -n "$EXISTING_ROWS" && "$EXISTING_ROWS" != "0" && "$FORCE" != "1" ]]; then
  echo "error: audit_receipts already has $EXISTING_ROWS row(s) in this database." >&2
  echo "       Restoring on top of existing data risks a primary-key collision" >&2
  echo "       partway through (pg_dump's INSERTs, not upserts) or silently" >&2
  echo "       duplicating rows. If you really mean to restore anyway (e.g. you" >&2
  echo "       know this is the same data, or you've already truncated the" >&2
  echo "       tables you want overwritten), re-run with --force." >&2
  exit 1
fi

TMP_SQL_GZ="$(mktemp)"
trap 'rm -f "$TMP_SQL_GZ"' EXIT

echo "==> Decrypting $ENC_FILE ..."
sops --input-type binary --output-type binary --decrypt "$ENC_FILE" > "$TMP_SQL_GZ"

echo "==> Restoring into ${POSTGRES_DB} (as ${POSTGRES_USER}) ..."
if gunzip -c "$TMP_SQL_GZ" | $COMPOSE exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"; then
  echo "==> Restore complete."
else
  echo "error: restore failed partway through -- see psql output above. The" >&2
  echo "       database may now be in a partially-restored state; inspect it" >&2
  echo "       directly before retrying." >&2
  exit 1
fi
