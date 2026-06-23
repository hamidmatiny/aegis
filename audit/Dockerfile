FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY audit/go.mod ./
COPY audit/ ./
RUN CGO_ENABLED=0 go build -o /audit ./cmd/audit

FROM alpine:3.20
COPY --from=builder /audit /usr/local/bin/audit
EXPOSE 8084
ENTRYPOINT ["audit"]
