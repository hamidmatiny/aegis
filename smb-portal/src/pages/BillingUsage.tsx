import { useEffect, useState } from "react";
import { smbApi } from "../api/client";
import type { UsageSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { UsageChart } from "../components/UsageChart";

export function BillingUsage() {
  const { usage: cachedUsage, me } = useAuth();
  const [usage, setUsage] = useState<UsageSummary | null>(cachedUsage);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!cachedUsage);
  const [billingBusy, setBillingBusy] = useState(false);

  const isCustomer = me?.role === "customer";
  const isPaid = isCustomer && me.tier === "premium";

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await smbApi.usage();
        if (!cancelled) setUsage(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [me?.role]);

  async function handleUpgrade() {
    setBillingBusy(true);
    setError(null);
    try {
      const { checkout_url } = await smbApi.checkout();
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBillingBusy(false);
    }
  }

  async function handleManageBilling() {
    setBillingBusy(true);
    setError(null);
    try {
      const { portal_url } = await smbApi.billingPortal();
      window.location.href = portal_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBillingBusy(false);
    }
  }

  return (
    <section className="page dashboard-page">
      <header className="page-header">
        <h1>Billing</h1>
        <p className="page-subtitle">
          Your plan, usage, and payment settings in one place.
        </p>
      </header>

      {isCustomer ? (
        <div className="card plan-card">
          <div className="plan-card-head">
            <div>
              <p className="eyebrow">Current plan</p>
              <h2 className="plan-name">{isPaid ? "Premium" : "Free"}</h2>
              <p className="plan-desc">
                {isPaid
                  ? "Guided walkthroughs and higher token limits are active."
                  : "Upgrade for guided walkthroughs and higher token limits."}
              </p>
            </div>
            {isPaid ? (
              <button
                type="button"
                className="btn-secondary"
                disabled={billingBusy}
                onClick={handleManageBilling}
              >
                {billingBusy ? "Opening…" : "Manage billing"}
              </button>
            ) : (
              <button type="button" className="btn-primary" disabled={billingBusy} onClick={handleUpgrade}>
                {billingBusy ? "Redirecting…" : "Upgrade"}
              </button>
            )}
          </div>
        </div>
      ) : null}

      {loading ? <p className="muted">Loading usage…</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {usage ? (
        <>
          <div className="metric-grid">
            <div className="card metric-card">
              <p className="metric-label">Q&A asks</p>
              <p className="metric-value">{usage.qa_ask_count}</p>
            </div>
            <div className="card metric-card">
              <p className="metric-label">Walkthrough grants</p>
              <p className="metric-value">{usage.walkthrough_grant_count}</p>
            </div>
            <div className="card metric-card">
              <p className="metric-label">Receipts matched</p>
              <p className="metric-value">{usage.receipts_matched}</p>
            </div>
            <div className={`card metric-card${usage.integrity === "ok" ? " metric-ok" : " metric-warn"}`}>
              <p className="metric-label">Integrity</p>
              <p className="metric-value metric-value-sm">{usage.integrity}</p>
            </div>
          </div>

          <div className="card">
            <h2 className="card-title">Usage over time</h2>
            <UsageChart usage={usage} />
          </div>

          {usage.integrity !== "ok" || usage.discrepancies.length > 0 ? (
            <div className="card alert-card" role="alert">
              <h2 className="card-title">Discrepancies</h2>
              <p className="card-desc">
                These usage events have no matching signed audit receipt — they should be
                investigated, not billed blindly.
              </p>
              <ul className="discrepancy-list">
                {usage.discrepancies.map((d) => (
                  <li key={d.usage_event_id}>
                    <strong>{d.event_type}</strong> · {d.reason}
                    {d.audit_receipt_id ? (
                      <span className="mono"> · receipt {d.audit_receipt_id}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="card success-card">
              <p>All usage events matched signed audit receipts.</p>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}
