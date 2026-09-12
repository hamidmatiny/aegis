-- Phase 12 fix-up: park pending tool calls for deferred human approval
ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS pending_approval JSONB;
