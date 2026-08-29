import { Link } from "react-router-dom";

const FEATURES = [
  {
    title: "Infrastructure Q&A",
    body: "Ask plain-language questions about your setup. Answers are grounded in the inventory you provide — databases, cloud, auth — not generic IT advice.",
  },
  {
    title: "CVE matching",
    body: "When you share what software you run, we cross-reference known vulnerabilities so you see relevant risks alongside each answer.",
  },
  {
    title: "Guided walkthroughs",
    body: "Paid plans unlock step-by-step remediation guidance for specific issues — not just a chat reply, but a structured path you can follow.",
  },
];

export function Landing() {
  return (
    <section className="page landing-page">
      <div className="landing-hero">
        <div className="landing-brand-row">
          <img src="/icon.svg" alt="AEGIS" width={48} height={48} className="landing-logo" />
          <p className="eyebrow">AEGIS for small business</p>
        </div>
        <h1>Security guidance built for owners, not security engineers</h1>
        <p className="lead">
          Tell us what you run. Ask questions in plain English. Get answers tied to
          your actual infrastructure — with honest CVE context and optional guided
          walkthroughs when you need more than a quick reply.
        </p>
        <div className="landing-cta-block">
          <Link className="btn-primary btn-lg" to="/register">
            Sign up — it&apos;s free to start
          </Link>
          <p className="guest-link">
            Already have an account? <Link to="/login">Sign in</Link>
            <span className="sep">·</span>
            <Link to="/onboarding" className="guest-secondary">
              Continue as guest
            </Link>
          </p>
        </div>
      </div>

      <div className="feature-grid">
        {FEATURES.map((f) => (
          <article key={f.title} className="card feature-card">
            <h2>{f.title}</h2>
            <p>{f.body}</p>
          </article>
        ))}
      </div>

      <div className="card landing-footnote">
        <p>
          Built on the same AEGIS policy engine and audit primitives that power our
          open-source LLM defense platform — packaged for teams without a dedicated
          security staff.
        </p>
      </div>
    </section>
  );
}
