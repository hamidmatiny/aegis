FROM golang:1.27-alpine AS builder
WORKDIR /src
COPY policy-engine/go.mod policy-engine/go.sum* ./
RUN go mod download
COPY policy-engine/ ./
RUN CGO_ENABLED=0 go build -o /policy-engine ./cmd/policy-engine

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
WORKDIR /app
COPY --from=builder /policy-engine /usr/local/bin/policy-engine
COPY policy-engine/policies /etc/aegis/policies
ENV AEGIS_POLICY_DIR=/etc/aegis/policies
EXPOSE 8081
RUN addgroup -g 10001 -S aegis && adduser -S -u 10001 -G aegis aegis
USER aegis

ENTRYPOINT ["policy-engine"]
