#!/bin/sh
set -eu
HTML_ROOT=/usr/share/nginx/html

# Inject first-party pageview beacon into every HTML shell (homepage + route shells).
inject_first_party() {
  f="$1"
  [ -f "$f" ] || return 0
  if grep -q 'aegis-pv-beacon' "$f" 2>/dev/null; then
    return 0
  fi
  # shellcheck disable=SC2016
  snip='<script id="aegis-pv-beacon">(()=>{try{const b=JSON.stringify({path:location.pathname,referrer:document.referrer||"",title:document.title||""});fetch("/api/smb/analytics/collect",{method:"POST",headers:{"Content-Type":"application/json"},body:b,keepalive:true}).catch(()=>{});}catch(e){}})();</script>'
  # Insert before </body>
  tmp="${f}.tmp"
  # Busybox sed: write to temp then mv
  awk -v snip="$snip" '
    /<\/body>/ && !done { print snip; done=1 }
    { print }
  ' "$f" > "$tmp" && mv "$tmp" "$f"
}

# Optional Cloudflare Web Analytics when CF_WEB_ANALYTICS_TOKEN is provided at runtime.
inject_cf() {
  f="$1"
  token="${CF_WEB_ANALYTICS_TOKEN:-}"
  [ -n "$token" ] || return 0
  [ -f "$f" ] || return 0
  if grep -q 'cloudflareinsights.com/beacon' "$f" 2>/dev/null; then
    return 0
  fi
  snip="<script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{\"token\":\"${token}\"}'></script>"
  tmp="${f}.tmp"
  awk -v snip="$snip" '
    /<\/body>/ && !done { print snip; done=1 }
    { print }
  ' "$f" > "$tmp" && mv "$tmp" "$f"
}

find "$HTML_ROOT" -name 'index.html' | while read -r html; do
  inject_first_party "$html"
  inject_cf "$html"
done

exec nginx -g 'daemon off;'
