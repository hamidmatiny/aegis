-- SMB Copilot: seeded CVE reference for free-tier Q&A matching
-- Numbered 007 (004_smb_usage_events.sql already exists under deploy/postgres/init/).

CREATE TABLE IF NOT EXISTS cve_reference (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_pattern  TEXT NOT NULL,
    cve_id           TEXT NOT NULL,
    severity         TEXT NOT NULL,
    summary          TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (product_pattern, cve_id)
);

CREATE INDEX IF NOT EXISTS idx_cve_reference_product_pattern
    ON cve_reference (product_pattern);

INSERT INTO cve_reference (product_pattern, cve_id, severity, summary)
VALUES
    (
        'postgres-16.x',
        'CVE-2024-10979',
        'HIGH',
        'PostgreSQL 16.x: privilege escalation via crafted PL/pgSQL function (illustrative seed for SMB Copilot matching).'
    ),
    (
        'postgres-16.2.x',
        'CVE-2024-10979',
        'HIGH',
        'PostgreSQL 16.2.x line inherits the illustrative CVE-2024-10979 advisory seed.'
    ),
    (
        'aws-eks',
        'CVE-2024-21626',
        'HIGH',
        'Kubernetes/container runtime escape class advisory commonly relevant to EKS workloads (illustrative seed).'
    ),
    (
        'mysql-8.x',
        'CVE-2024-20971',
        'MEDIUM',
        'MySQL 8.x server vulnerability class (illustrative seed for normalized mysql-8.x profiles).'
    )
ON CONFLICT (product_pattern, cve_id) DO NOTHING;
