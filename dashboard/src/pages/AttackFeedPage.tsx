import { useCallback, useEffect, useState } from "react";
import { auditApi, formatTime, isBlockedReceipt } from "../api/client";
import type { AuditReceipt } from "../types";

function actionBadge(receipt: AuditReceipt) {
  const p =
    receipt.policy_decision ??
    receipt.input_verdict ??
    receipt.output_verdict ??
    receipt.tool_decision;
  const action = String(p?.action ?? p?.status ?? receipt.event_type).toUpperCase();
  if (action.includes("BLOCK") || action.includes("DENIED")) {
    return <span className="badge badge-block">{action}</span>;
  }
  if (action.includes("ESCALATE") || action.includes("AWAITING")) {
    return <span className="badge badge-escalate">{action}</span>;
  }
  return <span className="badge badge-ok">{action}</span>;
}

export function AttackFeedPage() {
  const [receipts, setReceipts] = useState<AuditReceipt[]>([]);
  const [selected, setSelected] = useState<AuditReceipt | null>(null);
  const [verify, setVerify] = useState<{ valid: boolean; reason?: string } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await auditApi.query({ tenant_id: "default", limit: "50" });
      const blocked = resp.receipts.filter(isBlockedReceipt);
      setReceipts(blocked.length > 0 ? blocked : resp.receipts);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load receipts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 15000);
    return () => clearInterval(timer);
  }, [load]);

  async function selectReceipt(receipt: AuditReceipt) {
    setSelected(receipt);
    setVerify(null);
    try {
      setVerify(await auditApi.verify(receipt.receipt_id));
    } catch (e) {
      setVerify({ valid: false, reason: e instanceof Error ? e.message : "verify failed" });
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Attack Feed</h1>
        <button className="btn" type="button" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      <p className="muted">
        Recent blocked, denied, and escalated decisions from the audit service (auto-refreshes every 15s).
      </p>

      {error && <div className="error">{error}</div>}

      <div className="grid-2">
        <div className="panel">
          {loading ? (
            <p className="muted">Loading…</p>
          ) : receipts.length === 0 ? (
            <p className="muted">No receipts yet. Run the audit pipeline E2E script to seed data.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Trace</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {receipts.map((r) => (
                  <tr
                    key={r.receipt_id}
                    style={{ cursor: "pointer" }}
                    onClick={() => void selectReceipt(r)}
                  >
                    <td>{formatTime(r.created_at)}</td>
                    <td>{r.event_type}</td>
                    <td className="muted">{r.trace?.trace_id ?? "—"}</td>
                    <td>{actionBadge(r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="panel receipt-detail">
          <h3 style={{ marginTop: 0 }}>Receipt detail</h3>
          {!selected ? (
            <p className="muted">Select a receipt to inspect detector breakdown and verification status.</p>
          ) : (
            <>
              <p>
                <strong>{selected.receipt_id}</strong>
              </p>
              {verify && (
                <p>
                  Verify:{" "}
                  {verify.valid ? (
                    <span className="badge badge-ok">valid</span>
                  ) : (
                    <span className="badge badge-block">{verify.reason ?? "invalid"}</span>
                  )}
                </p>
              )}
              <pre>{JSON.stringify(selected, null, 2)}</pre>
            </>
          )}
        </div>
      </div>
    </>
  );
}
