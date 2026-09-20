-- Typed funnel events for Growth conversion (signup → Q&A → upgrade).
CREATE TABLE IF NOT EXISTS smb_funnel_events (
    id BIGSERIAL PRIMARY KEY,
    event TEXT NOT NULL,
    path TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS smb_funnel_events_event_created_idx
    ON smb_funnel_events (event, created_at DESC);

CREATE INDEX IF NOT EXISTS smb_funnel_events_session_created_idx
    ON smb_funnel_events (session_id, created_at DESC);
