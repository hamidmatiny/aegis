-- AEGIS Stage 0: core schema for audit logs and policy storage

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS audit_receipts (
    receipt_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id        TEXT NOT NULL,
    event_type       TEXT NOT NULL,
    trace_id         TEXT,
    request_id       TEXT,
    policy_pack_id   TEXT,
    policy_pack_version TEXT,
    payload          JSONB NOT NULL,
    payload_hash     BYTEA NOT NULL,
    signer_key_id    TEXT NOT NULL,
    signature        BYTEA NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_receipts_tenant_created
    ON audit_receipts (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_receipts_trace
    ON audit_receipts (trace_id);

CREATE TABLE IF NOT EXISTS policy_packs (
    id          TEXT NOT NULL,
    version     TEXT NOT NULL,
    tenant_id   TEXT NOT NULL DEFAULT 'default',
    content     JSONB NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, version, tenant_id)
);

CREATE TABLE IF NOT EXISTS attack_patterns (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pattern_hash TEXT NOT NULL UNIQUE,
    embedding   vector(384),
    source      TEXT,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attack_patterns_embedding
    ON attack_patterns USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
