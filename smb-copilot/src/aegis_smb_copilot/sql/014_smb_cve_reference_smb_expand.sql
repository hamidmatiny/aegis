-- Expand curated CVE/advisory coverage for common SMB free-tier questions.
-- Idempotent; applied at smb-copilot startup via migrate.py.
INSERT INTO cve_reference (product_pattern, cve_id, severity, summary)
VALUES
    ('microsoft-365', 'GENERIC-ADVISORY-M365', 'HIGH',
     'Generic advisory: enforce MFA / Security Defaults on Microsoft 365, block legacy auth, and review admin role holders — operational guidance, not a single product CVE.'),
    ('office365', 'GENERIC-ADVISORY-M365', 'HIGH',
     'Generic advisory: enforce MFA / Security Defaults on Microsoft 365 (Office 365), block legacy auth, and review admin role holders.'),
    ('m365', 'GENERIC-ADVISORY-M365', 'HIGH',
     'Generic advisory: enforce MFA / Security Defaults on M365, block legacy auth, and review admin role holders.'),
    ('windows-rdp', 'GENERIC-ADVISORY-RDP', 'HIGH',
     'Generic advisory: do not expose RDP (3389) to the public internet; prefer VPN or Azure Bastion / RD Gateway, enforce NLA + MFA, and keep the host patched.'),
    ('windows-server', 'GENERIC-ADVISORY-RDP', 'HIGH',
     'Generic advisory: harden Windows Server remote access — avoid public RDP, patch promptly, and restrict admin accounts.'),
    ('ubuntu-20.04', 'GENERIC-ADVISORY-UBUNTU', 'MEDIUM',
     'Generic advisory: Ubuntu 20.04 is past standard support in many environments — enable ESM or upgrade, and apply unattended-upgrades for security patches.'),
    ('ubuntu-22.04', 'GENERIC-ADVISORY-UBUNTU', 'MEDIUM',
     'Generic advisory: keep Ubuntu 22.04 patched via unattended-upgrades; review open SSH and unused services.'),
    ('ubuntu', 'GENERIC-ADVISORY-UBUNTU', 'MEDIUM',
     'Generic advisory: keep Ubuntu LTS hosts patched; prefer private networks for databases and admin ports.'),
    ('php-8.x', 'CVE-2024-4577', 'CRITICAL',
     'PHP CGI argument-injection class (CVE-2024-4577) — relevant when PHP is exposed via CGI on Windows; review PHP version and CGI usage on Linux hosts too.'),
    ('php-8.1.x', 'CVE-2024-4577', 'CRITICAL',
     'PHP CGI argument-injection class (CVE-2024-4577) — upgrade PHP and avoid exposing CGI to the internet.'),
    ('php-8.2.x', 'CVE-2024-4577', 'CRITICAL',
     'PHP CGI argument-injection class (CVE-2024-4577) — upgrade PHP and avoid exposing CGI to the internet.')
ON CONFLICT (product_pattern, cve_id) DO NOTHING;
