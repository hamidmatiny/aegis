# Shared schemas

Protobuf definitions and JSON Schema mirrors for all AEGIS cross-service messages.

## Generate code

```bash
make proto
```

Requires [buf](https://buf.build/docs/installation).

## Layout

```
shared/
├── proto/aegis/v1/     # Protobuf service + message definitions
├── jsonschema/v1/      # JSON Schema mirrors for REST/OpenAPI
├── gen/go/             # Generated Go + gRPC code
└── gen/python/         # Generated Python + gRPC code
```

## Core messages

- `Request` — gateway entry point
- `InputVerdict` — fused input defense result
- `PolicyDecision` — CEL policy evaluation
- `OutputVerdict` — fused output defense result
- `ToolCallRequest` — agent tool/MCP call
- `AuditReceipt` — signed audit record
