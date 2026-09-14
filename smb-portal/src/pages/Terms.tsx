import { Link } from "react-router-dom";

export function Terms() {
  return (
    <section className="page legal-page">
      <header className="page-hero">
        <h1>Terms of Use</h1>
        <p className="muted">Last updated: 2026-09-14 · Applies to defenseaegis.org (AEGIS SMB Copilot)</p>
      </header>
      <div className="panel stack legal-body">
        <p>
          By using AEGIS SMB Copilot you agree to these terms. If you do not agree,
          do not use the service.
        </p>
        <h2>Advisory only</h2>
        <p>
          Answers and walkthroughs are informational security guidance. They are not
          a formal security assessment, penetration test, legal advice, or a guarantee
          that your systems are safe. You remain responsible for changes you make to
          your infrastructure.
        </p>
        <h2>Accounts</h2>
        <p>
          Keep your credentials confidential. Guest sessions are for evaluation and
          may have limits. Paid features (including guided walkthroughs) require an
          active Standard subscription billed via Stripe.
        </p>
        <h2>Acceptable use</h2>
        <p>
          Do not use the service to attack systems you do not own, to distribute
          malware, or to paste secrets (passwords, private keys, live API tokens)
          into prompts or inventory fields.
        </p>
        <h2>Availability</h2>
        <p>
          The service is provided as-is. We may change features, limits, or pricing
          with notice on the site or by email when practical.
        </p>
        <h2>Contact</h2>
        <p>
          <a href="mailto:hamidmatiny@gmail.com">hamidmatiny@gmail.com</a> ·{" "}
          <Link to="/privacy">Privacy Policy</Link>
        </p>
      </div>
    </section>
  );
}
