-- Phase 12 CEO: queue rank for corp_reprioritize (queued tasks only)
ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS queue_position INTEGER;

CREATE INDEX IF NOT EXISTS idx_tasks_queue_position
    ON tasks (queue_position ASC NULLS LAST)
    WHERE status = 'queued';
