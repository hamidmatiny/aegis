FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY agent-gate/go.mod ./
COPY agent-gate/ ./
RUN CGO_ENABLED=0 go build -o /agent-gate ./cmd/agent-gate

FROM alpine:3.20
COPY --from=builder /agent-gate /usr/local/bin/agent-gate
EXPOSE 8083
ENTRYPOINT ["agent-gate"]
