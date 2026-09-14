import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useGuestSession } from "../auth/useGuestSession";
import { AssistantChat } from "../components/assistant/AssistantChat";

type PaywallState = {
  message?: string;
  question?: string;
};

export function WalkthroughPaywall() {
  const { me } = useAuth();
  const guest = useGuestSession();
  const location = useLocation();
  const state = (location.state ?? {}) as PaywallState;
  const denied = Boolean(state.message);
  const hasAccess = me?.role === "customer" || guest;

  if (!hasAccess) {
    return (
      <div className="assistant-page assistant-page--narrow">
        <section className="auth-card card">
          <header className="auth-card-head">
            <h1>Guided walkthrough</h1>
            <p className="muted">
              <Link to="/login">Sign in</Link> or{" "}
              <Link to="/onboarding">complete guest onboarding</Link> first.
            </p>
          </header>
        </section>
      </div>
    );
  }

  if (denied) {
    return (
      <div className="assistant-page assistant-page--narrow">
        <section className="auth-card card paywall">
          <header className="auth-card-head">
            <h1>Upgrade required</h1>
            <p>{state.message}</p>
          </header>
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
        </section>
      </div>
    );
  }

  return <AssistantChat walkthroughMode />;
}
