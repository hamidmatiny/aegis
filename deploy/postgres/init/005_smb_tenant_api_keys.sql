-- SMB Copilot: per-tenant API key hashes (plaintext returned once at register)
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS api_key_hash TEXT UNIQUE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_api_key_hash
    ON tenants (api_key_hash)
    WHERE api_key_hash IS NOT NULL;
