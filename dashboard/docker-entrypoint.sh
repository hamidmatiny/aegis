#!/bin/sh
set -eu

AUTH_FILE=/etc/nginx/.htpasswd
CONF=/etc/nginx/conf.d/default.conf
USER="${AEGIS_DASHBOARD_USER:-admin}"
PASSWORD="${AEGIS_DASHBOARD_PASSWORD:-}"

# There is no static default credential. If no password is supplied via the
# environment, generate a fresh random one for this container's lifetime and
# print it once so it's never silently open and never a guessable constant.
if [ -z "$PASSWORD" ]; then
  PASSWORD="$(openssl rand -hex 16)"
  echo "=================================================================="
  echo " AEGIS_DASHBOARD_PASSWORD was not set — generated one for this run:"
  echo ""
  echo "   user:     $USER"
  echo "   password: $PASSWORD"
  echo ""
  echo " This password will change on the next container restart. Set"
  echo " AEGIS_DASHBOARD_USER / AEGIS_DASHBOARD_PASSWORD in .env to persist"
  echo " it (see scripts/generate-credentials.sh)."
  echo "=================================================================="
fi

# BusyBox htpasswd: -c create, -b batch (non-interactive), -B bcrypt
htpasswd -cbB "$AUTH_FILE" "$USER" "$PASSWORD"
sed -i 's/# __AUTH_BASIC_FILE__ /auth_basic_user_file /' "$CONF"
sed -i 's/# __AUTH_BASIC__ /auth_basic /' "$CONF"
echo "dashboard auth enabled for user=$USER"

exec nginx -g 'daemon off;'
