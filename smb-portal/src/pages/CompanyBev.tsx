import { useEffect, useState } from "react";

type BevSummary = {
  total_agents: number;
  by_status: {
    idle: number;
    running: number;
    escalated: number;
    error: number;
  };
  tasks_completed_today: number;
  escalations_open: number;
  departments: { department: string; agent_count: number }[];
};

type PendingApproval = {
  tool_name?: string;
  arguments?: Record<string, unknown>;
  approval_request_id?: string;
  risk_level?: string;
  parked_at?: string;
};

type DeptAgent = {
  agent_id: string;
  team: string;
  role: string;
  status: string;
  model_provider: string;
  model_name: string;
  schedule: string;
  most_recent_task: {
    task_id: string;
    input: string;
    status: string;
    result: string | null;
    pending_approval: PendingApproval | null;
    created_at: string | null;
    completed_at: string | null;
  } | null;
};

type PendingRow = {
  task_id: string;
  department: string;
  team: string;
  pending_approval: PendingApproval;
  created_at: string | null;
};

const CORP_BASE = "/api/corp";

async function corpGet<T>(path: string): Promise<T> {
  const resp = await fetch(`${CORP_BASE}${path}`, { credentials: "include" });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  return resp.json() as Promise<T>;
}

async function corpPost<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${CORP_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  return resp.json() as Promise<T>;
}

export function CompanyBev() {
  const [summary, setSummary] = useState<BevSummary | null>(null);
  const [department, setDepartment] = useState<string | null>(null);
  const [agents, setAgents] = useState<DeptAgent[]>([]);
  const [pending, setPending] = useState<PendingRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);

  async function loadSummary() {
    setLoading(true);
    setError(null);
    try {
      const [data, pend] = await Promise.all([
        corpGet<BevSummary>("/v1/bev/summary"),
        corpGet<{ pending: PendingRow[] }>("/v1/tasks/pending"),
      ]);
      setSummary(data);
      setPending(pend.pending);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }

  async function loadDepartment(dept: string) {
    setDepartment(dept);
    setError(null);
    try {
      const data = await corpGet<{ department: string; agents: DeptAgent[] }>(
        `/v1/bev/departments/${encodeURIComponent(dept)}`,
      );
      setAgents(data.agents);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setAgents([]);
    }
  }

  async function decide(taskId: string, approved: boolean) {
    setActing(taskId);
    setError(null);
    try {
      await corpPost(`/v1/tasks/${taskId}/decide`, {
        approved,
        comment: approved ? "approved from BEV" : "denied from BEV",
      });
      await loadSummary();
      if (department) await loadDepartment(department);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setActing(null);
    }
  }

  useEffect(() => {
    void loadSummary();
  }, []);

  return (
    <section className="page">
      <header className="page-hero">
        <h1>Company — Bird&apos;s Eye View</h1>
        <p>
          Live agent corporation status from corp-orchestrator. Idle means no run yet —
          this page never invents activity. Escalated tools wait here until you approve.
        </p>
        <button type="button" className="text-btn" onClick={() => void loadSummary()}>
          Refresh
        </button>
      </header>

      {loading ? <p className="muted">Loading…</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {pending.length > 0 ? (
        <div className="panel" style={{ marginBottom: "1.5rem" }}>
          <h2>Pending approvals</h2>
          <ul className="admin-list">
            {pending.map((p) => (
              <li key={p.task_id} style={{ marginBottom: "1rem" }}>
                <strong>
                  {p.department}/{p.team}
                </strong>{" "}
                <span className="muted small">{p.created_at}</span>
                <div className="small">
                  Tool: <code>{p.pending_approval?.tool_name}</code> · risk{" "}
                  {p.pending_approval?.risk_level} · approval{" "}
                  <code>{p.pending_approval?.approval_request_id}</code>
                </div>
                <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>
                  {JSON.stringify(p.pending_approval?.arguments ?? {}, null, 2).slice(0, 600)}
                </pre>
                <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
                  <button
                    type="button"
                    className="text-btn"
                    disabled={acting === p.task_id}
                    onClick={() => void decide(p.task_id, true)}
                  >
                    {acting === p.task_id ? "Working…" : "Approve & execute"}
                  </button>
                  <button
                    type="button"
                    className="text-btn"
                    disabled={acting === p.task_id}
                    onClick={() => void decide(p.task_id, false)}
                  >
                    Deny
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {summary ? (
        <div className="panel">
          <h2>Company</h2>
          <ul className="admin-list">
            <li>
              <strong>Total agents:</strong> {summary.total_agents}
            </li>
            <li>
              <strong>Idle:</strong> {summary.by_status.idle} ·{" "}
              <strong>Running:</strong> {summary.by_status.running} ·{" "}
              <strong>Escalated:</strong> {summary.by_status.escalated} ·{" "}
              <strong>Error:</strong> {summary.by_status.error}
            </li>
            <li>
              <strong>Tasks completed today:</strong> {summary.tasks_completed_today}
            </li>
            <li>
              <strong>Open escalations:</strong> {summary.escalations_open}
            </li>
          </ul>
          <h3>Departments</h3>
          <ul className="admin-list">
            {summary.departments.map((d) => (
              <li key={d.department}>
                <button
                  type="button"
                  className={`linkish${department === d.department ? " active" : ""}`}
                  onClick={() => void loadDepartment(d.department)}
                >
                  <strong>{d.department}</strong>
                  <span className="muted"> · {d.agent_count} agents</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {department ? (
        <div className="panel" style={{ marginTop: "1.5rem" }}>
          <h2>{department}</h2>
          {agents.length === 0 ? (
            <p className="muted">No agents in this department.</p>
          ) : (
            <ul className="admin-list">
              {agents.map((a) => (
                <li key={a.agent_id} style={{ marginBottom: "1rem" }}>
                  <strong>{a.team}</strong> <span className="muted">({a.status})</span>
                  <div className="muted small">
                    {a.model_provider}/{a.model_name} · cron {a.schedule}
                  </div>
                  <div className="small">{a.role}</div>
                  {a.most_recent_task ? (
                    <div className="panel" style={{ marginTop: "0.5rem" }}>
                      <div className="muted small">
                        Latest task · {a.most_recent_task.status} ·{" "}
                        {a.most_recent_task.created_at}
                      </div>
                      {a.most_recent_task.pending_approval ? (
                        <div style={{ marginTop: "0.5rem" }}>
                          <div className="small">
                            Pending: <code>{a.most_recent_task.pending_approval.tool_name}</code>
                          </div>
                          <button
                            type="button"
                            className="text-btn"
                            disabled={acting === a.most_recent_task.task_id}
                            onClick={() => void decide(a.most_recent_task!.task_id, true)}
                          >
                            Approve & execute
                          </button>
                        </div>
                      ) : null}
                      <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
                        {(a.most_recent_task.result || a.most_recent_task.input || "").slice(
                          0,
                          800,
                        )}
                      </pre>
                    </div>
                  ) : (
                    <p className="muted small">No tasks yet — idle.</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </section>
  );
}
