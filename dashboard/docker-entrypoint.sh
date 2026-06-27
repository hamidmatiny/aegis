#!/bin/sh
set -eu

AUTH_FILE=/etc/nginx/.htpasswd
CONF=/etc/nginx/conf.d/default.conf

if [ -n "${AEGIS_DASHBOARD_PASSWORD:-}" ]; then
  USER="${AEGIS_DASHBOARD_USER:-admin}"
  # BusyBox htpasswd: -b batch, -B bcrypt
  htpasswd -cbB "$AUTH_FILE" "$USER" "$AEGIS_DASHBOARD_PASSWORD"
  sed -i 's/# __AUTH_BASIC_FILE__ /auth_basic_user_file /' "$CONF"
  sed -i 's/# __AUTH_BASIC__ /auth_basic /' "$CONF"
  echo "dashboard auth enabled for user=$USER"
else
  echo "WARNING: AEGIS_DASHBOARD_PASSWORD unset — dashboard is open (dev-only)" >&2
fi

exec nginx -g 'daemon off;'
