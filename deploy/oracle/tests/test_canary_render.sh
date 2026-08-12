#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"

bash generate-canary-nginx.sh

if ! grep -q "location = /.env.bak" nginx-demo-canary.conf; then
  echo "Missing /.env.bak canary block" >&2
  exit 1
fi
if ! grep -q "location = /.git-credentials" nginx-demo-canary.conf; then
  echo "Missing /.git-credentials canary block" >&2
  exit 1
fi
if ! grep -q "###CANARY_BLOCK###" nginx-demo.conf.template; then
  echo "Template missing placeholder ###CANARY_BLOCK###" >&2
  exit 1
fi

python3 <<'PY'
from pathlib import Path
root = Path('.')
text = root.joinpath('nginx-demo.conf.template').read_text()
canary = root.joinpath('nginx-demo-canary.conf').read_text()
out = text.replace('###CANARY_BLOCK###', canary)
if '###CANARY_BLOCK###' in out:
    raise SystemExit('placeholder still present after replacement')
print('render OK')
PY

echo "canary render tests OK"
