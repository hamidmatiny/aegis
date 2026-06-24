import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { pct, redteamApi } from "../api/client";
import type { CampaignSummary } from "../types";

export function AsrTrendsPage() {
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const resp = await redteamApi.listCampaigns();
      setCampaigns(resp.campaigns);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load campaigns");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const trendData = useMemo(
    () =>
      [...campaigns]
        .reverse()
        .map((c) => ({
          id: c.campaign_id.replace("camp-", ""),
          overall: Number((c.bypass_rate * 100).toFixed(1)),
          input:
            c.by_target.input_defense != null
              ? Number((c.by_target.input_defense.bypass_rate * 100).toFixed(1))
              : 0,
          output:
            c.by_target.output_defense != null
              ? Number((c.by_target.output_defense.bypass_rate * 100).toFixed(1))
              : 0,
        })),
    [campaigns],
  );

  const latestByTarget = useMemo(() => {
    if (campaigns.length === 0) return [];
    const latest = campaigns[0];
    return Object.values(latest.by_target).map((t) => ({
      target: t.target.replace("_defense", ""),
      asr: Number((t.bypass_rate * 100).toFixed(1)),
    }));
  }, [campaigns]);

  async function runQuickCampaign() {
    setRunning(true);
    setError("");
    try {
      await redteamApi.runCampaign();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Campaign failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>ASR Trends</h1>
        <button
          className="btn btn-primary"
          type="button"
          disabled={running}
          onClick={() => void runQuickCampaign()}
        >
          {running ? "Running…" : "Run quick campaign"}
        </button>
      </div>
      <p className="muted">
        Attack Success Rate (bypass rate) from red-team campaigns in this session. Historical persistence is planned for a later stage.
      </p>
      {error && <div className="error">{error}</div>}

      {campaigns.length === 0 ? (
        <div className="panel">
          <p className="muted">No campaigns in this red-team session. Run a quick campaign or use the red-team API.</p>
        </div>
      ) : (
        <>
          <div className="stat-row" style={{ marginBottom: "1rem" }}>
            <div className="stat">
              <div className="stat-label">Latest overall ASR</div>
              <div className="stat-value">{pct(campaigns[0].bypass_rate)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Probes (latest)</div>
              <div className="stat-value">{campaigns[0].total_probes}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Bypasses (latest)</div>
              <div className="stat-value">{campaigns[0].bypass_count}</div>
            </div>
          </div>

          <div className="panel">
            <h3 style={{ marginTop: 0 }}>ASR over campaigns (session)</h3>
            <div style={{ width: "100%", height: 280 }}>
              <ResponsiveContainer>
                <LineChart data={trendData}>
                  <CartesianGrid stroke="#2a3548" />
                  <XAxis dataKey="id" stroke="#94a3b8" />
                  <YAxis unit="%" stroke="#94a3b8" />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="overall" name="Overall" stroke="#3b82f6" />
                  <Line type="monotone" dataKey="input" name="Input defense" stroke="#22c55e" />
                  <Line type="monotone" dataKey="output" name="Output defense" stroke="#f59e0b" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel">
            <h3 style={{ marginTop: 0 }}>Latest campaign by defense layer</h3>
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={latestByTarget}>
                  <CartesianGrid stroke="#2a3548" />
                  <XAxis dataKey="target" stroke="#94a3b8" />
                  <YAxis unit="%" stroke="#94a3b8" />
                  <Tooltip />
                  <Bar dataKey="asr" name="ASR %" fill="#ef4444" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel">
            <table>
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th>Started</th>
                  <th>Probes</th>
                  <th>Bypasses</th>
                  <th>ASR</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.campaign_id}>
                    <td>{c.campaign_id}</td>
                    <td>{new Date(c.started_at).toLocaleString()}</td>
                    <td>{c.total_probes}</td>
                    <td>{c.bypass_count}</td>
                    <td>{pct(c.bypass_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
