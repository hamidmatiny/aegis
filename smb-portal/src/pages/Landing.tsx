import { Link } from "react-router-dom";

const STEPS = [
  {
    n: "1",
    title: "Tell us what you run",
    body: "Describe your stack in plain language — databases, cloud, auth — during setup. We use that inventory to ground later answers.",
  },
  {
    n: "2",
    title: "Ask in plain English",
    body: "Questions like “should I expose Postgres to the internet?” get answers tied to what you said you run, not generic IT blog posts.",
  },
  {
    n: "3",
    title: "Get answers with CVE context",
    body: "When a match exists in our curated vulnerability reference for your stack, we surface severity and a short summary next to the answer.",
  },
];

const FEATURES = [
  {
    title: "Infrastructure Q&A",
    body: "Plain-language questions about your setup. Answers are grounded in the inventory you provide — not one-size-fits-all advice.",
  },
  {
    title: "CVE matching",
    body: "We match what you run against a curated vulnerability reference for common SMB stack components (not a live full-NVD feed). Relevant hits appear beside answers when they exist.",
  },
  {
    title: "Guided walkthroughs",
    body: "Paid plan ($29 CAD/mo): longer, step-by-step remediation guidance for a specific issue. Free accounts get Q&A; walkthroughs unlock after upgrade.",
    badge: "Paid",
  },
];

export function Landing() {
  return (
    <div className="landing">
      <section className="landing-hero" aria-labelledby="landing-hero-title">
        <div className="landing-hero-copy">
          <p className="landing-kicker">AEGIS for small business</p>
          <h1 id="landing-hero-title">
            Security guidance for owners — not security engineers
          </h1>
          <p className="lead">
            Tell us what you run. Ask in plain English. Get answers tied to your
            actual infrastructure, with honest vulnerability context when we have
            a match.
          </p>
          <div className="landing-cta-row">
            <Link className="btn-primary btn-lg" to="/register">
              Sign up — free to start
            </Link>
            <Link className="btn-secondary btn-lg" to="/login">
              Sign in
            </Link>
          </div>
          <p className="guest-link">
            Prefer to try first?{" "}
            <Link to="/onboarding" className="guest-secondary">
              Continue as guest
            </Link>
          </p>
        </div>
        <div className="landing-hero-visual" aria-hidden="false">
          <ProductPreview />
        </div>
      </section>

      <section id="how-it-works" className="landing-section" aria-labelledby="how-title">
        <h2 id="how-title">How it works</h2>
        <p className="section-lead">Three steps. No security degree required.</p>
        <ol className="how-steps">
          {STEPS.map((s) => (
            <li key={s.n} className="how-step">
              <span className="how-step-n" aria-hidden="true">
                {s.n}
              </span>
              <div>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-section" aria-labelledby="features-title">
        <h2 id="features-title">What you get</h2>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <article key={f.title} className="card feature-card">
              <div className="feature-card-head">
                <h3>{f.title}</h3>
                {"badge" in f && f.badge ? (
                  <span className="plan-pill feature-badge">{f.badge}</span>
                ) : null}
              </div>
              <p>{f.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="pricing" className="landing-section" aria-labelledby="pricing-title">
        <h2 id="pricing-title">Simple pricing</h2>
        <p className="section-lead">
          Stripe billing. Cancel anytime from the billing portal after upgrade.
        </p>
        <div className="pricing-grid">
          <article className="card pricing-card">
            <h3>Free</h3>
            <p className="price-line">
              <span className="price-amount">$0</span>
            </p>
            <ul className="price-list">
              <li>Infrastructure inventory setup</li>
              <li>Plain-language Q&amp;A</li>
              <li>Curated CVE matches when available</li>
            </ul>
            <Link className="btn-secondary" to="/register">
              Create free account
            </Link>
          </article>
          <article className="card pricing-card pricing-card-featured">
            <h3>Standard</h3>
            <p className="price-line">
              <span className="price-amount">$29</span>
              <span className="price-unit">CAD / month</span>
            </p>
            <ul className="price-list">
              <li>Everything in Free</li>
              <li>Guided walkthroughs (step-by-step remediation)</li>
              <li>Stronger walkthrough model when enabled</li>
            </ul>
            <Link className="btn-primary" to="/register">
              Sign up, then upgrade
            </Link>
          </article>
        </div>
      </section>

      <section id="trust" className="landing-section landing-trust" aria-labelledby="trust-title">
        <h2 id="trust-title">Privacy &amp; data handling</h2>
        <div className="card trust-card">
          <ul className="trust-list">
            <li>
              <span className="trust-check" aria-hidden="true">
                ✓
              </span>
              <span>
                We store the infrastructure inventory and questions you submit so
                answers can stay grounded in your setup.
              </span>
            </li>
            <li>
              <span className="trust-check" aria-hidden="true">
                ✓
              </span>
              <span>
                We never ask you to paste production passwords, API keys, or SSH
                private keys — and we do not store credentials of that kind.
              </span>
            </li>
            <li>
              <span className="trust-check" aria-hidden="true">
                ✓
              </span>
              <span>
                Answers are advisory only. They do not change your systems.
                Usage is recorded with an Ed25519-signed audit trail on the AEGIS
                stack.
              </span>
            </li>
          </ul>
          <p className="muted small trust-more">
            Full detail: <Link to="/privacy">Privacy Policy</Link> ·{" "}
            <Link to="/terms">Terms of Use</Link>
          </p>
        </div>
      </section>

      <section className="landing-section landing-oss" aria-labelledby="oss-title">
        <h2 id="oss-title">Open foundation</h2>
        <p>
          Built on the same open AEGIS policy engine (CEL) and audit primitives as
          our LLM-defense platform — packaged for teams without a dedicated
          security staff.
        </p>
        <a
          className="btn-secondary"
          href="https://github.com/hamidmatiny/aegis"
          target="_blank"
          rel="noopener noreferrer"
        >
          View the open-source repo on GitHub
        </a>
      </section>

      <footer className="landing-footer">
        <div className="landing-footer-grid">
          <div>
            <p className="footer-brand">AEGIS</p>
            <p className="muted small">Security guidance for small-business owners.</p>
          </div>
          <nav className="footer-nav" aria-label="Footer">
            <a href="#how-it-works">How it works</a>
            <a href="#pricing">Pricing</a>
            <Link to="/privacy">Privacy</Link>
            <Link to="/terms">Terms</Link>
            <a
              href="https://github.com/hamidmatiny/aegis"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
            <a href="mailto:hamidmatiny@gmail.com">Support</a>
          </nav>
        </div>
        <p className="muted small footer-copy">
          © {new Date().getFullYear()} AEGIS. Advisory security guidance — not a
          substitute for a security assessment.
        </p>
      </footer>
    </div>
  );
}

function ProductPreview() {
  return (
    <figure className="product-preview">
      <figcaption className="product-preview-caption">
        Product preview — Q&amp;A as it appears after setup
      </figcaption>
      <div className="product-preview-frame">
        <div className="product-preview-chrome">
          <span />
          <span />
          <span />
          <strong>Q&amp;A</strong>
        </div>
        <div className="product-preview-body">
          <div className="bubble user">
            <p className="bubble-label">You</p>
            <p>We run Postgres on a VPS. Should it be reachable from the public internet?</p>
          </div>
          <div className="bubble assistant">
            <p className="bubble-label">AEGIS</p>
            <p>
              Prefer private networking or a firewall allow-list. Exposing Postgres
              on 0.0.0.0:5432 is a common SMB misconfiguration — lock it down unless
              you have a specific, monitored need.
            </p>
            <ul className="cve-list">
              <li>
                <strong className="mono">GENERIC-ADVISORY-POSTGRES-EXPOSE</strong>{" "}
                [high] on postgres: Prefer not exposing the database port publicly.
              </li>
            </ul>
            <p className="disclaimer muted small">
              Advisory only — verify against your environment before changing
              production.
            </p>
          </div>
        </div>
      </div>
    </figure>
  );
}
