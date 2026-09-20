import { Link } from "react-router-dom";

const STEPS = [
  {
    n: "1",
    title: "Point your app at the gateway",
    body: "Drop-in OpenAI-compatible base URL between your application and any LLM provider — no rewrite of your existing SDK calls.",
  },
  {
    n: "2",
    title: "Enforce policy as code",
    body: "CEL policies classify every tool call into LOW / MEDIUM / HIGH / IRREVERSIBLE. High-risk actions wait for a human before they run.",
  },
  {
    n: "3",
    title: "Keep a tamper-evident trail",
    body: "Every decision is recorded with Ed25519-signed audit receipts in Postgres — so you can prove what was allowed, blocked, or escalated.",
  },
];

const FEATURES = [
  {
    title: "Policy-as-code (CEL)",
    body: "Tenant overrides and risk tiers live in CEL — not buried in prompt text. Same engine AEGIS uses for its own governed agent loops.",
  },
  {
    title: "Human gate for high-risk tools",
    body: "Agent-gate blocks irreversible or credential-touching tool calls until a reviewer allows them. Defense against tool/MCP abuse, not just prompt injection.",
  },
  {
    title: "Tamper-evident audit",
    body: "Ed25519-signed receipts for allow / deny / escalate decisions. Built for operators who need evidence, not vibes.",
  },
];

export function Landing() {
  return (
    <div className="landing">
      <section className="landing-hero" aria-labelledby="landing-hero-title">
        <div className="landing-hero-copy">
          <p className="landing-kicker">LLM security gateway</p>
          <h1 id="landing-hero-title">
            Enforce policy between your app and any LLM
          </h1>
          <p className="lead">
            AEGIS is an open-source enforcer/gateway: CEL policy-as-code, human
            approval for high-risk tool calls, and Ed25519 audit trails — sitting
            between your application and whatever model provider you use.
          </p>
          <div className="landing-cta-row">
            <a
              className="btn-primary btn-lg"
              href="https://github.com/hamidmatiny/aegis"
              target="_blank"
              rel="noopener noreferrer"
            >
              View on GitHub
            </a>
            <Link className="btn-secondary btn-lg" to="/login">
              Sign in
            </Link>
          </div>
          <p className="guest-link">
            Self-host the gateway:{" "}
            <a
              href="https://github.com/hamidmatiny/aegis#readme"
              target="_blank"
              rel="noopener noreferrer"
              className="guest-secondary"
            >
              clone and run <code>./scripts/demo.sh</code>
            </a>
          </p>
        </div>
        <div className="landing-hero-visual" aria-hidden="false">
          <ProductPreview />
        </div>
      </section>

      <section id="how-it-works" className="landing-section" aria-labelledby="how-title">
        <h2 id="how-title">How it works</h2>
        <p className="section-lead">
          Application → gateway → provider. Policy and audit on every hop.
        </p>
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
              </div>
              <p>{f.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section
        id="applied-example"
        className="landing-section"
        aria-labelledby="applied-title"
      >
        <h2 id="applied-title">Applied example on this stack</h2>
        <p className="section-lead">
          defenseaegis.org also hosts an advisory Q&amp;A surface built on the
          same policy and audit primitives — not the core product.
        </p>
        <div className="feature-grid">
          <article className="card feature-card">
            <div className="feature-card-head">
              <h3>Infrastructure Q&amp;A</h3>
            </div>
            <p>
              Plain-language questions grounded in an inventory you provide.
              Answers are advisory only — they do not change your systems.
            </p>
          </article>
          <article className="card feature-card">
            <div className="feature-card-head">
              <h3>Guided walkthroughs</h3>
              <span className="plan-pill feature-badge">Optional</span>
            </div>
            <p>
              Longer step-by-step remediation guidance ($29 CAD/mo). Same audit
              trail; still advisory — not autonomous action-taking.
            </p>
          </article>
        </div>
        <div className="landing-cta-row" style={{ marginTop: "1.25rem" }}>
          <Link className="btn-secondary" to="/register">
            Try the Q&amp;A example — free to start
          </Link>
        </div>
      </section>

      <section id="pricing" className="landing-section" aria-labelledby="pricing-title">
        <h2 id="pricing-title">Q&amp;A example pricing</h2>
        <p className="section-lead">
          Pricing below is for the hosted advisory Q&amp;A surface only. The
          enforcer/gateway is open source — self-host from GitHub.
        </p>
        <div className="pricing-grid">
          <article className="card pricing-card">
            <h3>Free</h3>
            <p className="price-line">
              <span className="price-amount">$0</span>
            </p>
            <ul className="price-list">
              <li>Infrastructure inventory setup</li>
              <li>Plain-language advisory Q&amp;A</li>
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
              <li>Guided walkthroughs (step-by-step, advisory)</li>
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
                Self-hosted gateway traffic stays on your infrastructure. The
                hosted Q&amp;A example stores the inventory and questions you
                submit so answers stay grounded.
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
                Q&amp;A answers are advisory only. They do not change your
                systems. Gateway allow/deny decisions and Q&amp;A usage are
                recorded with an Ed25519-signed audit trail.
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
          AEGIS is open source — CEL policy engine, agent-gate, input/output
          defense, and audit primitives under one monorepo. Comparable category:
          LLM Guard / Rebuff / Vigil-class defenses, with tool-call governance.
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
            <p className="muted small">
              LLM security gateway — policy, audit, human gate.
            </p>
          </div>
          <nav className="footer-nav" aria-label="Footer">
            <a href="#how-it-works">How it works</a>
            <a href="#applied-example">Q&amp;A example</a>
            <a href="#pricing">Pricing</a>
            <Link to="/guides/smb-cve-exposure-checklist">Guides</Link>
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
          © {new Date().getFullYear()} AEGIS. Enforcer/gateway is open source;
          hosted Q&amp;A is advisory — not a substitute for a security
          assessment.
        </p>
      </footer>
    </div>
  );
}

function ProductPreview() {
  return (
    <figure className="product-preview">
      <figcaption className="product-preview-caption">
        Gateway path — app → AEGIS → provider
      </figcaption>
      <div className="product-preview-frame">
        <div className="product-preview-chrome">
          <span />
          <span />
          <span />
          <strong>agent-gate</strong>
        </div>
        <div className="product-preview-body">
          <div className="bubble user">
            <p className="bubble-label">Tool call</p>
            <p>
              <code className="mono">shell.exec</code> —{" "}
              <code className="mono">rm -rf /data/prod</code>
            </p>
          </div>
          <div className="bubble assistant">
            <p className="bubble-label">AEGIS</p>
            <p>
              Risk <strong>IRREVERSIBLE</strong>. Policy requires human approval
              before execution. Request held — no side effects until a reviewer
              allows.
            </p>
            <ul className="cve-list">
              <li>
                <strong className="mono">AUDIT</strong> Ed25519 receipt queued ·
                decision=pending_approval
              </li>
            </ul>
            <p className="disclaimer muted small">
              Defense-in-depth: input defense → CEL → model router → output
              defense → agent-gate → audit.
            </p>
          </div>
        </div>
      </div>
    </figure>
  );
}
