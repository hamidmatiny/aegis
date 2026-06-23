FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY gateway/go.mod gateway/go.sum* ./
RUN go mod download 2>/dev/null || true
COPY gateway/ ./
RUN CGO_ENABLED=0 go build -o /gateway ./cmd/gateway

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=builder /gateway /usr/local/bin/gateway
EXPOSE 8080
ENTRYPOINT ["gateway"]
