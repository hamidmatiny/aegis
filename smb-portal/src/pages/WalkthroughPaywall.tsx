import { Link, useLocation } from "react-router-dom";
import { loadGuestSession } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ChatPanel } from "../components/ChatPanel";

type PaywallState = {
  message?: string;
  question?: string;
};

export function WalkthroughPaywall() {
  const { me } = useAuth();
  const guest = loadGuestSession();
  const location = useLocation();
  const state = (location.state ?? {}) as PaywallState;
  const denied = Boolean(state.message);
  const hasAccess = me?.role === "customer" || guest;

  if (!hasAccess) {
    return (
      <section className="page">
        <header className="page-hero">
          <h1>Guided walkthrough</h1>
          <p>
            <Link to="/login">Sign in</Link> or{" "}
            <Link to="/onboarding">complete guest onboarding</Link> first.
          </p>
        </header>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-hero">
        <h1>Guided walkthrough</h1>
        <p>Paid-tier feature. Free plans receive an upgrade prompt instead of an error.</p>
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
              Guided walkthroughs are not included on your current plan. Upgrade
              your subscription or contact your administrator to unlock this feature.
            </p>
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
            Submit a walkthrough request. If your tenant is on the free tier, you
            will see the upgrade prompt.
          </p>
          <ChatPanel walkthroughMode />
        </div>
      )}
    </section>
  );
}
