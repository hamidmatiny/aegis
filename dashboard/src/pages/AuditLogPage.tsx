import { useCallback, useEffect, useState } from "react";
import { auditApi, formatTime } from "../api/client";
import type { AuditReceipt } from "../types";

export function AuditLogPage() {
  const [tenantId, setTenantId] = useState("default");
  const [eventType, setEventType] = useState("");
  const [traceId, setTraceId] = useState("");
  const [receipts, setReceipts] = useState<AuditReceipt[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const search = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string> = { tenant_id: tenantId, limit: "100" };
      if (eventType) params.event_type = eventType;
      if (traceId) params.trace_id = traceId;
      const resp = await auditApi.query(params);
      setReceipts(resp.receipts);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, [tenantId, eventType, traceId]);

  useEffect(() => {
    void search();
  }, [search]);

  async function exportJson() {
    setError("");
    try {
      const resp = await auditApi.export({
        tenant_id: tenantId,
        format: "json",
        event_type: eventType || undefined,
      });
      if (!resp.ok) throw new Error(await resp.text());
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "audit-export.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Audit Log</h1>
        <button className="btn btn-primary" type="button" onClick={() => void exportJson()}>
          Export JSON
        </button>
      </div>

      <div className="filters panel">
        <input
          placeholder="Tenant ID"
          value={tenantId}
          onChange={(e) => setTenantId(e.target.value)}
        />
        <select value={eventType} onChange={(e) => setEventType(e.target.value)}>
          <option value="">All event types</option>
          <option value="INPUT_DEFENSE">INPUT_DEFENSE</option>
          <option value="OUTPUT_DEFENSE">OUTPUT_DEFENSE</option>
          <option value="POLICY_DECISION">POLICY_DECISION</option>
          <option value="TOOL_GATE">TOOL_GATE</option>
        </select>
        <input
          placeholder="Trace ID"
          value={traceId}
          onChange={(e) => setTraceId(e.target.value)}
        />
        <button className="btn" type="button" disabled={loading} onClick={() => void search()}>
          Search
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Event</th>
              <th>Trace</th>
              <th>Receipt ID</th>
            </tr>
          </thead>
          <tbody>
            {receipts.length === 0 ? (
              <tr>
                <td colSpan={4} className="muted">
                  No receipts match your filters.
                </td>
              </tr>
            ) : (
              receipts.map((r) => (
                <tr key={r.receipt_id}>
                  <td>{formatTime(r.created_at)}</td>
                  <td>{r.event_type}</td>
                  <td>{r.trace?.trace_id ?? "—"}</td>
                  <td className="muted">{r.receipt_id}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
