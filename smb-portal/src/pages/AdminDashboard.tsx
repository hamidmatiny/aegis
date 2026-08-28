import { useEffect, useState } from "react";
import { smbApi } from "../api/client";

type TenantRow = {
  id: string;
  slug: string;
  tier: string;
  email: string | null;
  walkthrough_allowed: boolean | null;
};

export function AdminDashboard() {
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Awaited<
    ReturnType<typeof smbApi.adminTenantDetail>
  > | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const data = await smbApi.adminListTenants();
        setTenants(data.tenants);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  async function loadDetail(tenantId: string) {
    setSelectedId(tenantId);
    setDetail(null);
    try {
      const data = await smbApi.adminTenantDetail(tenantId);
      setDetail(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function flipTier(tier: "free" | "paid") {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      await smbApi.adminSetTier(selectedId, tier);
      const data = await smbApi.adminTenantDetail(selectedId);
      setDetail(data);
      const list = await smbApi.adminListTenants();
      setTenants(list.tenants);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <header className="page-hero">
        <h1>Operator console</h1>
        <p>Tenant list, usage, and walkthrough tier control.</p>
      </header>

      {error ? <p className="error">{error}</p> : null}

      <div className="admin-grid">
        <div className="panel">
          <h2>Tenants</h2>
          <ul className="admin-list">
            {tenants.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  className={`linkish${selectedId === t.id ? " active" : ""}`}
                  onClick={() => loadDetail(t.id)}
                >
                  <strong>{t.slug}</strong>
                  {t.email ? <span className="muted"> · {t.email}</span> : null}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="panel">
          <h2>Tenant detail</h2>
          {!detail ? (
            <p className="muted">Select a tenant to view usage and tier controls.</p>
          ) : (
            <>
              <p>
                <strong>{detail.slug}</strong> · tier {detail.tier}
              </p>
              <p>
                Walkthrough:{" "}
                <strong>{detail.walkthrough_allowed ? "allowed" : "blocked"}</strong>
              </p>
              <p className="mono small">{detail.policy_override_path}</p>
              <div className="stat-row">
                <div className="stat">
                  <span>Q&A asks</span>
                  <strong>{detail.usage.qa_ask_count}</strong>
                </div>
                <div className="stat">
                  <span>Walkthrough grants</span>
                  <strong>{detail.usage.walkthrough_grant_count}</strong>
                </div>
              </div>
              <div className="row-actions">
                <button
                  type="button"
                  className="button"
                  disabled={busy || detail.walkthrough_allowed}
                  onClick={() => flipTier("paid")}
                >
                  Enable paid walkthrough
                </button>
                <button
                  type="button"
                  className="button secondary"
                  disabled={busy || !detail.walkthrough_allowed}
                  onClick={() => flipTier("free")}
                >
                  Revert to free tier
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
