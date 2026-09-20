import { Link } from "react-router-dom";

export function Privacy() {
  return (
    <section className="page legal-page">
      <header className="page-hero">
        <h1>Privacy Policy</h1>
        <p className="muted">Last updated: 2026-09-20 · Applies to defenseaegis.org (AEGIS)</p>
      </header>
      <div className="panel stack legal-body">
        <p>
          AEGIS is an open-source LLM security gateway. defenseaegis.org also hosts
          an advisory Q&amp;A surface as an applied example on the same stack. This
          policy describes what we collect for that hosted site.
        </p>
        <h2>What we collect</h2>
        <ul>
          <li>
            Account details you provide (email, password hash) when you register.
          </li>
          <li>
            Infrastructure inventory and onboarding answers you submit so Q&amp;A can
            stay grounded in your setup.
          </li>
          <li>
            Questions you ask and the answers returned, for product operation and
            usage metering.
          </li>
          <li>
            Billing metadata from Stripe when you upgrade (customer and subscription
            identifiers) — card numbers are handled by Stripe, not stored by us.
          </li>
        </ul>
        <h2>What we do not collect</h2>
        <ul>
          <li>
            We do not ask for, and do not intend to store, production passwords, API
            keys, SSH private keys, or similar credentials. Do not paste them into
            chat or inventory fields.
          </li>
        </ul>
        <h2>How we use data</h2>
        <p>
          To provide Q&amp;A and walkthroughs, enforce plan limits, bill paid plans,
          improve reliability, and keep an audit trail of usage events (Ed25519-signed
          receipts on the AEGIS stack).
        </p>
        <h2>Sharing</h2>
        <p>
          We use processors required to run the service (for example hosting and
          Stripe for payments). We do not sell your inventory or chat content.
        </p>
        <h2>Contact</h2>
        <p>
          Questions:{" "}
          <a href="mailto:hamidmatiny@gmail.com">hamidmatiny@gmail.com</a>. See also{" "}
          <Link to="/terms">Terms of Use</Link>.
        </p>
      </div>
    </section>
  );
}
