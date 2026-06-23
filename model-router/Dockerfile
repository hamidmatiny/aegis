FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY model-router/go.mod ./
COPY model-router/ ./
RUN CGO_ENABLED=0 go build -o /model-router ./cmd/model-router

FROM alpine:3.20
COPY --from=builder /model-router /usr/local/bin/model-router
EXPOSE 8082
ENTRYPOINT ["model-router"]
