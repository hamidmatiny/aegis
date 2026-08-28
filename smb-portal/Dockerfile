FROM node:20-alpine AS build
WORKDIR /app
ARG VITE_BASE_PATH=/
ARG VITE_API_BASE=/api/smb
ENV VITE_BASE_PATH=$VITE_BASE_PATH
ENV VITE_API_BASE=$VITE_API_BASE
COPY smb-portal/package.json smb-portal/package-lock.json* ./
RUN npm install
COPY smb-portal/ .
RUN npm run build

FROM nginx:1.31-alpine
COPY smb-portal/nginx.conf /etc/nginx/conf.d/default.conf
COPY smb-portal/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3001

# Non-root nginx (same pattern as dashboard/). Port 3001 needs no privileged bind.
RUN sed -i 's#^pid[[:space:]].*#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
    && grep -q '^pid /tmp/nginx.pid;' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /etc/nginx/conf.d /var/cache/nginx /var/log/nginx /docker-entrypoint.sh

USER nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
