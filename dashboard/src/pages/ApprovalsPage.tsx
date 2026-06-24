import { useCallback, useEffect, useState } from "react";
import { agentGateApi, formatTime } from "../api/client";
import type { ApprovalRequest } from "../types";

export function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const resp = await agentGateApi.listApprovals(showAll ? "all" : "pending");
      setApprovals(resp.approvals);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load approvals");
    }
  }, [showAll]);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(id: string, approved: boolean) {
    setBusyId(id);
    setError("");
    try {
      await agentGateApi.decide(id, approved, "dashboard-operator", approved ? "approved via dashboard" : "denied via dashboard");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed");
    } finally {
      setBusyId("");
    }
  }

  async function seedPending() {
    setError("");
    try {
      await agentGateApi.createPendingApproval();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create test approval");
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Approval Inbox</h1>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button className="btn" type="button" onClick={() => setShowAll((v) => !v)}>
            {showAll ? "Pending only" : "Show all"}
          </button>
          <button className="btn btn-primary" type="button" onClick={() => void seedPending()}>
            Create test approval
          </button>
        </div>
      </div>
      <p className="muted">Human-in-the-loop decisions for irreversible agent-gate actions.</p>
      {error && <div className="error">{error}</div>}

      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Tool</th>
              <th>Risk</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {approvals.length === 0 ? (
              <tr>
                <td colSpan={5} className="muted">
                  No approval requests. Trigger one with an irreversible tool evaluation or use &quot;Create test approval&quot;.
                </td>
              </tr>
            ) : (
              approvals.map((a) => (
                <tr key={a.approval_id}>
                  <td>
                    <strong>{a.tool_call.tool_name}</strong>
                    <div className="muted">{a.approval_id}</div>
                  </td>
                  <td>{a.tool_call.risk_level ?? "—"}</td>
                  <td>
                    <span
                      className={`badge ${
                        a.status.includes("AWAITING")
                          ? "badge-pending"
                          : a.status.includes("APPROVED")
                            ? "badge-ok"
                            : "badge-block"
                      }`}
                    >
                      {a.status}
                    </span>
                  </td>
                  <td>{formatTime(a.created_at)}</td>
                  <td>
                    {a.status.includes("AWAITING") ? (
                      <div style={{ display: "flex", gap: "0.35rem" }}>
                        <button
                          className="btn btn-ok"
                          type="button"
                          disabled={busyId === a.approval_id}
                          onClick={() => void decide(a.approval_id, true)}
                        >
                          Approve
                        </button>
                        <button
                          className="btn btn-danger"
                          type="button"
                          disabled={busyId === a.approval_id}
                          onClick={() => void decide(a.approval_id, false)}
                        >
                          Deny
                        </button>
                      </div>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
