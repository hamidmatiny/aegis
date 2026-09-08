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
    <section className="page">
      <header className="page-hero">
        <h1>Usage & billing</h1>
        <p>
          Counts from <code>usage_events</code>, cross-checked against signed
          audit receipts. Upgrade unlocks guided walkthroughs via Stripe Checkout.
        </p>
      </header>

      {isCustomer ? (
        <div className="panel billing-actions">
          {isPaid ? (
            <>
              <p className="ok">Plan: <strong>Premium</strong> — walkthroughs enabled.</p>
              <button type="button" className="button secondary" disabled={billingBusy} onClick={handleManageBilling}>
                {billingBusy ? "Opening…" : "Manage billing"}
              </button>
            </>
          ) : (
            <>
              <p>Free plan — upgrade for guided walkthroughs and higher token limits.</p>
              <button type="button" className="button" disabled={billingBusy} onClick={handleUpgrade}>
                {billingBusy ? "Redirecting…" : "Upgrade via Stripe"}
              </button>
            </>
          )}
        </div>
      ) : null}

      {loading ? <p className="muted">Loading usage…</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {usage ? (
        <>
          <div className="stat-row">
            <div className="stat">
              <span>Q&A asks</span>
              <strong>{usage.qa_ask_count}</strong>
            </div>
            <div className="stat">
              <span>Walkthrough grants</span>
              <strong>{usage.walkthrough_grant_count}</strong>
            </div>
            <div className="stat">
              <span>Receipts matched</span>
              <strong>{usage.receipts_matched}</strong>
            </div>
            <div className={`stat ${usage.integrity === "ok" ? "ok-stat" : "warn-stat"}`}>
              <span>Integrity</span>
              <strong>{usage.integrity}</strong>
            </div>
          </div>

          <div className="panel">
            <h2>Usage chart</h2>
            <UsageChart usage={usage} />
          </div>

          {usage.integrity !== "ok" || usage.discrepancies.length > 0 ? (
            <div className="panel discrepancy-panel" role="alert">
              <h2>Discrepancies</h2>
              <p>
                These <code>usage_events</code> rows have no matching signed
                audit receipt and should be investigated — not billed blindly.
              </p>
              <ul>
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
            <div className="panel ok-panel">
              <p>All usage events matched signed audit receipts.</p>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}
