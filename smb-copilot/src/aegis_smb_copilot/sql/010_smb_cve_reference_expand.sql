-- Expand SMB Copilot CVE reference beyond the illustrative 007 seed.
-- Curated static rows only — not a live NVD/sync feed. Rows marked GENERIC-ADVISORY-*
-- have no specific CVE ID when a product class has no single canonical CVE to cite.

INSERT INTO cve_reference (product_pattern, cve_id, severity, summary)
VALUES
    (
        'postgres-14.x',
        'CVE-2023-39417',
        'HIGH',
        'PostgreSQL 14.x: extension script privilege escalation (curated reference row).'
    ),
    (
        'postgres-15.x',
        'CVE-2023-5869',
        'HIGH',
        'PostgreSQL 15.x: memory allocation issue enabling privilege escalation (curated reference row).'
    ),
    (
        'mariadb-10.x',
        'CVE-2024-21096',
        'MEDIUM',
        'MariaDB 10.x server vulnerability class (curated reference row).'
    ),
    (
        'mysql-5.7.x',
        'CVE-2024-20963',
        'MEDIUM',
        'MySQL 5.7.x server vulnerability class (curated reference row).'
    ),
    (
        'nginx-1.x',
        'CVE-2024-7347',
        'MEDIUM',
        'nginx 1.x: HTTP/3 QUIC vulnerability class (curated reference row).'
    ),
    (
        'apache-2.4.x',
        'CVE-2024-38476',
        'HIGH',
        'Apache httpd 2.4.x: mod_proxy SSRF/regression class (curated reference row).'
    ),
    (
        'wordpress-6.x',
        'CVE-2024-4439',
        'MEDIUM',
        'WordPress 6.x core XSS class advisory (curated reference row).'
    ),
    (
        'redis-7.x',
        'CVE-2024-31449',
        'HIGH',
        'Redis 7.x: Lua script remote code execution class (curated reference row).'
    ),
    (
        'kubernetes',
        'CVE-2024-3177',
        'MEDIUM',
        'Kubernetes: mount propagation / kubelet advisory class (curated reference row).'
    ),
    (
        'docker',
        'CVE-2024-21626',
        'HIGH',
        'Docker/container runtime: runc process.cwd container breakout class (curated reference row).'
    ),
    (
        'aws-rds',
        'GENERIC-ADVISORY-RDS',
        'MEDIUM',
        'Generic advisory: review AWS RDS patching, IAM database auth, and security-group exposure for your engine/version — no single CVE applies to all RDS deployments.'
    ),
    (
        'azure',
        'GENERIC-ADVISORY-AZURE',
        'MEDIUM',
        'Generic advisory: review Azure resource patching, managed identity scope, and NSG rules — no single CVE applies to all Azure workloads.'
    ),
    (
        'gcp',
        'GENERIC-ADVISORY-GCP',
        'MEDIUM',
        'Generic advisory: review GCP OS/config patching, service account keys, and VPC firewall rules — no single CVE applies to all GCP workloads.'
    ),
    (
        'digitalocean',
        'GENERIC-ADVISORY-DROPLET',
        'MEDIUM',
        'Generic advisory: review droplet base-image patching, SSH exposure, and firewall tags — no single CVE applies to all droplets.'
    ),
    (
        'auth0',
        'GENERIC-ADVISORY-SSO',
        'MEDIUM',
        'Generic advisory: review Auth0 tenant hardening (MFA, action secrets, callback URLs) — operational guidance, not a product CVE.'
    ),
    (
        'okta',
        'GENERIC-ADVISORY-SSO',
        'MEDIUM',
        'Generic advisory: review Okta app assignment, MFA policies, and API token rotation — operational guidance, not a product CVE.'
    ),
    (
        'cognito',
        'GENERIC-ADVISORY-SSO',
        'MEDIUM',
        'Generic advisory: review Cognito password policies, app client secrets, and hosted UI redirect allowlists — operational guidance, not a product CVE.'
    )
ON CONFLICT (product_pattern, cve_id) DO NOTHING;
