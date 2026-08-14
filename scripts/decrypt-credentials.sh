#!/usr/bin/env bash
# Recovers .env from its encrypted backup, .env.enc (see .sops.yaml for the
# one-time age/sops setup this depends on). Use this when:
#   - setting up a NEW box from an existing, already-committed .env.enc
#   - .env was lost on an existing box but .env.enc + the age key survived
#
# Requires SOPS_AGE_KEY_FILE (or the default ~/.config/sops/age/keys.txt)
# to point at the age PRIVATE key -- the one from `age-keygen`, never
# committed to this repo. Without it, decryption fails with a clear error;
# there is no fallback or default key baked in anywhere.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v sops >/dev/null 2>&1; then
  echo "error: sops is not installed. See .sops.yaml for setup." >&2
  exit 1
fi
if ! command -v age >/dev/null 2>&1; then
  echo "error: age is not installed. See .sops.yaml for setup." >&2
  exit 1
fi
if [ ! -f .env.enc ]; then
  echo "error: .env.enc not found in $ROOT -- nothing to decrypt." >&2
  echo "       (it's only created once scripts/generate-credentials.sh has" >&2
  echo "       been run with sops/age installed and a real age key configured" >&2
  echo "       in .sops.yaml -- see that file.)" >&2
  exit 1
fi
if [ -z "${SOPS_AGE_KEY_FILE:-}" ] && [ ! -f "$HOME/.config/sops/age/keys.txt" ]; then
  echo "error: no age private key found. Set SOPS_AGE_KEY_FILE to point at it," >&2
  echo "       e.g.:" >&2
  echo "         export SOPS_AGE_KEY_FILE=/path/to/age-key.txt" >&2
  echo "         ./scripts/decrypt-credentials.sh" >&2
  exit 1
fi

if [ -f .env ]; then
  echo "==> .env already exists -- refusing to overwrite it automatically."
  echo "    Move it aside first if you really want to restore from the backup:"
  echo "      mv .env .env.bak-\$(date +%s)"
  echo "      ./scripts/decrypt-credentials.sh"
  exit 1
fi

echo "==> Decrypting .env.enc -> .env ..."
sops --input-type dotenv --output-type dotenv --decrypt .env.enc > .env.tmp
mv .env.tmp .env
chmod 600 .env
echo "==> .env restored. If this is a live/already-running box (not a fresh"
echo "    setup), remember: POSTGRES_PASSWORD and AEGIS_AUDIT_SIGNING_KEY only"
echo "    take effect on a service's next full restart with a matching backing"
echo "    store -- a restored .env doesn't retroactively change what a running"
echo "    Postgres/audit instance already has. See the ALTER USER note in"
echo "    scripts/generate-credentials.sh if that applies here."
