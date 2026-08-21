FROM node:20-alpine AS build
WORKDIR /app
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm install
COPY dashboard/ .
RUN npm run build

FROM nginx:1.31-alpine
RUN apk add --no-cache apache2-utils openssl
COPY dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY dashboard/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3000

# Run fully as the non-root 'nginx' user (already present in the base
# image). Port 3000 needs no privileged bind. The entrypoint writes
# /etc/nginx/conf.d/default.conf (sed -i) and /etc/nginx/.htpasswd at
# startup, so both must be owned by the runtime user ahead of time.
#
# The pid path is moved to /tmp (world-writable) since /var/run
# isn't writable by a non-root user. The match pattern below is
# whitespace/path-tolerant on purpose: this image's actual nginx.conf
# says "pid /run/nginx.pid;" (no "/var"), not the "/var/run/..." path
# a literal match would expect, and that mismatch is exactly what broke
# this the first time -- the sed silently matched nothing and nginx
# still tried (and failed) to open /run/nginx.pid as non-root. The
# grep -q right after makes that class of failure fail the *build*
# instead of failing silently until the container starts.
RUN sed -i 's#^pid[[:space:]].*#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
    && grep -q '^pid /tmp/nginx.pid;' /etc/nginx/nginx.conf \
    && touch /etc/nginx/.htpasswd \
    && chown -R nginx:nginx /usr/share/nginx/html /etc/nginx/conf.d /var/cache/nginx /var/log/nginx /etc/nginx/.htpasswd /docker-entrypoint.sh

USER nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
