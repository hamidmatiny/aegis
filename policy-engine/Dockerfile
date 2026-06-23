FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY policy-engine/go.mod ./
COPY policy-engine/ ./
RUN CGO_ENABLED=0 go build -o /policy-engine ./cmd/policy-engine

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=builder /policy-engine /usr/local/bin/policy-engine
EXPOSE 8081
ENTRYPOINT ["policy-engine"]
