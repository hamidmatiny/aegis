-- Mark test/QA/automation tenants so headline MRR/signups exclude them.
-- Rows are never deleted; is_test_account=TRUE excludes them from BEV metrics.

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS is_test_account BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_tenants_is_test_account
    ON tenants (is_test_account)
    WHERE is_test_account = FALSE;

-- Historical backfill (fact-check 2026-09). Patterns must match
-- aegis_smb_session.test_accounts — review before extending.
UPDATE tenants t
SET is_test_account = TRUE
FROM customers c
WHERE c.tenant_id = t.id
  AND t.is_test_account = FALSE
  AND (
       lower(c.email) LIKE '%@example.com'
    OR lower(c.email) LIKE '%@example.test'
    OR lower(c.email) LIKE 'e2e-%'
    OR lower(c.email) LIKE 'e2e-so-%'
    OR lower(c.email) LIKE 'stripe-e2e-%'
    OR lower(c.email) LIKE 'stripe-check-%'
    OR lower(c.email) LIKE 'live-verify-%'
    OR lower(c.email) LIKE 'ask-check-%'
    OR lower(c.email) LIKE 'logout-check-%'
    OR lower(c.email) LIKE 'logout-fix+%'
    OR lower(c.email) LIKE 'avatar-diag+%'
    OR lower(c.email) LIKE 'landing-checkout+%'
    OR lower(c.email) LIKE 'landing-smoke+%'
    OR lower(c.email) LIKE 'mock%'
    OR lower(c.email) LIKE 'live0%'
    OR lower(c.email) LIKE 'prod-ask-%'
    OR lower(c.email) LIKE 'live-avatar-%'
  );

-- Slug-only tenants (onboarding API without customer email) + any remaining slug hits
UPDATE tenants t
SET is_test_account = TRUE
WHERE t.is_test_account = FALSE
  AND (
       lower(t.slug) LIKE 'stripe-e2e-%'
    OR lower(t.slug) LIKE 'stripe-check-%'
    OR lower(t.slug) LIKE 'live-verify-%'
    OR lower(t.slug) LIKE 'mock%'
    OR lower(t.slug) LIKE 'live0%'
    OR lower(t.slug) LIKE 'prod-ask-%'
    OR lower(t.slug) LIKE 'live-avatar-%'
    OR lower(t.slug) LIKE 'e2e-%'
    OR lower(t.slug) LIKE 'e2e-so-%'
    OR lower(t.slug) LIKE 'navtest-%'
    OR lower(t.slug) LIKE 'navptest-%'
    OR lower(t.slug) LIKE 'ask-%'
    OR lower(t.slug) LIKE 'logout-%'
    OR lower(t.slug) LIKE 'avatar-diag-%'
    OR lower(t.slug) LIKE 'ui-chk-%'
    OR lower(t.slug) LIKE 'ui-reg-%'
    OR lower(t.slug) LIKE 'ui-guest-%'
    OR lower(t.slug) LIKE 'dbg-guest-%'
    OR lower(t.slug) LIKE 'api-reg-%'
    OR lower(t.slug) LIKE 'landing-smoke-%'
  );
