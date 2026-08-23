-- SMB Copilot: per-tenant usage / billing events
CREATE TABLE IF NOT EXISTS usage_events (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id         UUID NOT NULL REFERENCES tenants (id),
    event_type        TEXT NOT NULL,
    audit_receipt_id  UUID,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_events_tenant_id
    ON usage_events (tenant_id);
