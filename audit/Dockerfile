FROM golang:1.24-alpine AS builder
WORKDIR /src
COPY audit/go.mod audit/go.sum ./
COPY audit/ ./
RUN CGO_ENABLED=0 go build -o /audit ./cmd/audit

FROM alpine:3.24
COPY --from=builder /audit /usr/local/bin/audit
EXPOSE 8084
RUN addgroup -g 10001 -S aegis && adduser -S -u 10001 -G aegis aegis
USER aegis

ENTRYPOINT ["audit"]
