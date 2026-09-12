-- Phase 12: autonomous agent corporation registry + task queue
CREATE TABLE IF NOT EXISTS agents (
    agent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department TEXT NOT NULL,
    team TEXT NOT NULL,
    role TEXT NOT NULL,
    model_provider TEXT NOT NULL DEFAULT 'mock',
    model_name TEXT NOT NULL DEFAULT 'mock-model',
    context_scope JSONB NOT NULL DEFAULT '{"allowed_tools":[],"denied_data_domains":[]}'::jsonb,
    status TEXT NOT NULL DEFAULT 'idle'
        CHECK (status IN ('idle', 'running', 'escalated', 'error')),
    schedule TEXT NOT NULL DEFAULT '0 * * * *',
    escalation_target TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (department, team)
);

CREATE INDEX IF NOT EXISTS idx_agents_department ON agents (department);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents (status);

CREATE TABLE IF NOT EXISTS tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents (agent_id) ON DELETE CASCADE,
    input TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'done', 'failed', 'escalated')),
    result TEXT,
    audit_receipt_id TEXT,
    pending_approval JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tasks_agent_id ON tasks (agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks (created_at DESC);
