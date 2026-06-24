FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY model-router/go.mod model-router/go.sum* ./
RUN go mod download
COPY model-router/ ./
RUN CGO_ENABLED=0 go build -o /model-router ./cmd/model-router

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
WORKDIR /app
COPY --from=builder /model-router /usr/local/bin/model-router
COPY model-router/config /etc/aegis/model-router
ENV AEGIS_MODEL_ROUTER_CONFIG=/etc/aegis/model-router/providers.yaml
EXPOSE 8082
ENTRYPOINT ["model-router"]
