import { Link, useLocation } from "react-router-dom";
import { loadSession } from "../api/client";
import { ChatPanel } from "../components/ChatPanel";

type PaywallState = {
  message?: string;
  upgradeHint?: string;
  question?: string;
};

export function WalkthroughPaywall() {
  const session = loadSession();
  const location = useLocation();
  const state = (location.state ?? {}) as PaywallState;
  const denied = Boolean(state.message);

  if (!session) {
    return (
      <section className="page">
        <header className="page-hero">
          <h1>Guided walkthrough</h1>
          <p>
            <Link to="/onboarding">Complete onboarding</Link> to request a
            walkthrough.
          </p>
        </header>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-hero">
        <h1>Guided walkthrough</h1>
        <p>
          Paid-tier feature gated by policy-engine CEL. Free tenants see an
          upgrade path instead of a bare error.
        </p>
      </header>

      {denied ? (
        <div className="panel paywall">
          <h2>Upgrade required</h2>
          <p>{state.message}</p>
          {state.question ? (
            <p className="muted">Requested for: “{state.question}”</p>
          ) : null}
          <div className="upgrade-box">
            <p>
              <strong>Upgrade call-to-action:</strong> enable paid walkthroughs
              for this tenant in policy-engine, then reload policy.
            </p>
            <p className="mono small">{state.upgradeHint}</p>
          </div>
          <div className="row-actions">
            <Link className="button secondary" to="/chat">
              Back to free Q&A
            </Link>
            <Link className="button" to="/billing">
              View usage
            </Link>
          </div>
        </div>
      ) : (
        <div className="panel">
          <p className="muted">
            Submit a walkthrough request. If your tenant is free-tier, you will
            land on the upgrade paywall.
          </p>
          <ChatPanel walkthroughMode />
        </div>
      )}
    </section>
  );
}
