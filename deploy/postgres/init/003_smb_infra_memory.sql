-- SMB Copilot: per-tenant infrastructure memory (embeddings)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS infra_memory (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id         UUID NOT NULL REFERENCES tenants (id),
    category          TEXT NOT NULL,
    normalized_value  TEXT NOT NULL,
    embedding         vector(1536) NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_infra_memory_tenant_id
    ON infra_memory (tenant_id);

CREATE INDEX IF NOT EXISTS idx_infra_memory_embedding_ivfflat
    ON infra_memory
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
