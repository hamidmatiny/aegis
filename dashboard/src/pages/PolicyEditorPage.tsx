import { useCallback, useEffect, useState } from "react";
import { policyApi } from "../api/client";
import type { DryRunResponse } from "../types";

const SAMPLE_INPUT = {
  action: "BLOCK",
  fused_score: 0.92,
  detector_scores: [{ detector_id: "heuristic", score: 0.92, reasoning: "dashboard preview" }],
};

export function PolicyEditorPage() {
  const [packId, setPackId] = useState("default");
  const [yaml, setYaml] = useState("");
  const [ruleSet, setRuleSet] = useState("input");
  const [result, setResult] = useState<DryRunResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadPack = useCallback(async (id: string) => {
    setError("");
    setResult(null);
    try {
      const resp = await policyApi.getPack(id);
      setYaml(resp.source_yaml);
      setPackId(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load policy pack");
    }
  }, []);

  useEffect(() => {
    void loadPack("default");
  }, [loadPack]);

  async function dryRun() {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const sample =
        ruleSet === "input"
          ? SAMPLE_INPUT
          : ruleSet === "output"
            ? { action: "BLOCK", fused_score: 0.85 }
            : { tool_name: "delete_file", risk_level: "IRREVERSIBLE" };
      setResult(
        await policyApi.dryRun({
          yaml,
          rule_set: ruleSet,
          sample,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dry-run failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Policy Editor</h1>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button className="btn" type="button" onClick={() => void loadPack(packId)}>
            Reload
          </button>
          <button className="btn btn-primary" type="button" disabled={loading} onClick={() => void dryRun()}>
            {loading ? "Evaluating…" : "Dry-run preview"}
          </button>
        </div>
      </div>
      <p className="muted">
        Edit policy pack YAML and preview CEL evaluation without persisting changes. To apply edits, update files under{" "}
        <code>policy-engine/policies/</code> and POST <code>/v1/reload</code>.
      </p>

      <div className="filters">
        <select value={packId} onChange={(e) => void loadPack(e.target.value)}>
          <option value="default">default</option>
        </select>
        <select value={ruleSet} onChange={(e) => setRuleSet(e.target.value)}>
          <option value="input">input rules</option>
          <option value="output">output rules</option>
          <option value="tool">tool rules</option>
        </select>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="grid-2">
        <div className="panel">
          <h3 style={{ marginTop: 0 }}>YAML</h3>
          <textarea value={yaml} onChange={(e) => setYaml(e.target.value)} spellCheck={false} />
        </div>
        <div className="panel">
          <h3 style={{ marginTop: 0 }}>Dry-run result</h3>
          {!result ? (
            <p className="muted">Run dry-run to validate YAML and preview the policy decision for a sample verdict.</p>
          ) : result.valid && result.decision ? (
            <>
              <p>
                Action: <span className="badge badge-block">{result.decision.action}</span>{" "}
                <span className="muted">mode={result.decision.mode}</span>
              </p>
              {result.decision.block_reason && <p>{result.decision.block_reason}</p>}
              <pre>{JSON.stringify(result.decision.matched_rules, null, 2)}</pre>
            </>
          ) : (
            <div className="error">{result.error ?? "Invalid policy YAML"}</div>
          )}
        </div>
      </div>
    </>
  );
}
