import { useEffect, useState } from "react";
import { policyApi } from "../api/client";
import type { PolicyRule } from "../types";

export function ToolMatrixPage() {
  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        const resp = await policyApi.getPack("default");
        setRules(resp.pack.tool_rules ?? []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load tool rules");
      }
    })();
  }, []);

  return (
    <>
      <div className="page-header">
        <h1>Tool Permission Matrix</h1>
      </div>
      <p className="muted">
        Agent-gate tool rules from the active policy pack. Enforcement is deterministic via policy-engine CEL evaluation.
      </p>
      {error && <div className="error">{error}</div>}

      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Rule</th>
              <th>CEL condition</th>
              <th>Action</th>
              <th>Enabled</th>
            </tr>
          </thead>
          <tbody>
            {rules.length === 0 ? (
              <tr>
                <td colSpan={4} className="muted">
                  No tool rules loaded.
                </td>
              </tr>
            ) : (
              rules.map((rule) => (
                <tr key={rule.id}>
                  <td>
                    <strong>{rule.name}</strong>
                    <div className="muted">{rule.id}</div>
                  </td>
                  <td>
                    <code>{rule.cel}</code>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        rule.action.includes("block")
                          ? "badge-block"
                          : rule.action.includes("escalate")
                            ? "badge-escalate"
                            : "badge-ok"
                      }`}
                    >
                      {rule.action}
                    </span>
                  </td>
                  <td>{rule.enabled ? "yes" : "no"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
