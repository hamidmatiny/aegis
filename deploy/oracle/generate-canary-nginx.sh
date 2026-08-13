#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="$ROOT/canary-config.yml"
OUT="$ROOT/nginx-demo-canary.conf"

print_block() {
  local path="$1"
  local target="$2"

  if [[ "$path" != /* ]]; then
    echo "Invalid canary path: $path" >&2
    exit 1
  fi
  if [[ ! "$target" =~ ^https:// ]]; then
    echo "Invalid canary target: $target" >&2
    exit 1
  fi

  cat <<EOF
    location = $path {
        if (\$request_method != GET) { return 404; }
        if (\$args) { return 404; }
        add_header Referrer-Policy "no-referrer";
        return 302 $target;
    }

EOF
}

if [ ! -f "$CFG" ]; then
  echo "# no canary config file found" > "$OUT"
  exit 0
fi

path=""
target=""
rm -f "$OUT"

while IFS= read -r raw_line; do
  line="${raw_line%%#*}"
  if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*path:[[:space:]]*(.*)$ ]]; then
    new_path="${BASH_REMATCH[1]}"
    if [[ -n "$path" && -n "$target" ]]; then
      print_block "$path" "$target" >> "$OUT"
    fi
    path="$new_path"
    target=""
  elif [[ "$line" =~ ^[[:space:]]*path:[[:space:]]*(.*)$ ]]; then
    path="${BASH_REMATCH[1]}"
  elif [[ "$line" =~ ^[[:space:]]*target:[[:space:]]*(.*)$ ]]; then
    target="${BASH_REMATCH[1]}"
  fi
  # ignore other lines

done < "$CFG"

if [[ -n "$path" && -n "$target" ]]; then
  print_block "$path" "$target" >> "$OUT"
fi

echo "Generated canary nginx config: $OUT"
