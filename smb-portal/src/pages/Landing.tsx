import { Link } from "react-router-dom";

export function Landing() {
  return (
    <section className="page landing">
      <header className="page-hero">
        <h1>AEGIS SMB Copilot</h1>
        <p>
          AI-assisted IT diagnostics for small teams — advisory Q&A grounded in
          your infrastructure inventory, with optional guided walkthroughs on paid
          plans.
        </p>
      </header>
      <div className="panel landing-actions">
        <Link className="button" to="/login">
          Sign in
        </Link>
        <Link className="button secondary" to="/onboarding">
          Continue as guest
        </Link>
        <p className="muted small">
          Guest mode uses the original onboarding flow with a browser-stored API
          key. Customer sign-in uses a secure session cookie instead.
        </p>
      </div>
    </section>
  );
}
