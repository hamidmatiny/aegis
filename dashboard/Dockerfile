FROM node:20-alpine AS build
WORKDIR /app
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm install
COPY dashboard/ .
RUN npm run build

FROM nginx:1.27-alpine
RUN apk add --no-cache apache2-utils
COPY dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY dashboard/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3000
ENTRYPOINT ["/docker-entrypoint.sh"]
