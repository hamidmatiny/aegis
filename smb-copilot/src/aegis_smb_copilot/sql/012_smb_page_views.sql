-- First-party privacy-light pageview log for Growth impact checks.
CREATE TABLE IF NOT EXISTS smb_page_views (
    id BIGSERIAL PRIMARY KEY,
    path TEXT NOT NULL,
    referrer TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    ua_hash TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS smb_page_views_path_created_idx
    ON smb_page_views (path, created_at DESC);
