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
    created_at: string | null;
    completed_at: string | null;
  } | null;
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

export function CompanyBev() {
  const [summary, setSummary] = useState<BevSummary | null>(null);
  const [department, setDepartment] = useState<string | null>(null);
  const [agents, setAgents] = useState<DeptAgent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadSummary() {
    setLoading(true);
    setError(null);
    try {
      const data = await corpGet<BevSummary>("/v1/bev/summary");
      setSummary(data);
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

  useEffect(() => {
    void loadSummary();
  }, []);

  return (
    <section className="page">
      <header className="page-hero">
        <h1>Company — Bird&apos;s Eye View</h1>
        <p>
          Live agent corporation status from corp-orchestrator. Idle means no run yet —
          this page never invents activity.
        </p>
        <button type="button" className="text-btn" onClick={() => void loadSummary()}>
          Refresh
        </button>
      </header>

      {loading ? <p className="muted">Loading…</p> : null}
      {error ? <p className="error">{error}</p> : null}

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
                  <strong>
                    {a.team}
                  </strong>{" "}
                  <span className="muted">({a.status})</span>
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
