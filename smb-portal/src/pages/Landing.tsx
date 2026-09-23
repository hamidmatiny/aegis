import { Link } from "react-router-dom";
import { InterceptionDemo } from "../components/InterceptionDemo";
import "./landing.css";

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

const PROOF = [
  {
    label: "Open source",
    value: "github.com/hamidmatiny/aegis",
    href: "https://github.com/hamidmatiny/aegis",
    detail: "Active monorepo — gateway, policy, gate, audit, CI.",
  },
  {
    label: "Awesome list",
    value: "emerging.md",
    href: "https://github.com/beyefendi/awesome-llm-security/blob/main/emerging.md",
    detail: "Listed under Agent Authorization in awesome-llm-security.",
  },
  {
    label: "External review",
    value: "Issue #63",
    href: "https://github.com/hamidmatiny/aegis/issues/63",
    detail: "Independent technical engagement on the audit boundary.",
  },
];

export function Landing() {
  return (
    <div className="lp">
      <a className="lp-skip" href="#how-it-works">
        Skip to how it works
      </a>

      <section className="lp-hero" aria-labelledby="landing-hero-title">
        <div className="lp-hero-inner">
          <div className="lp-hero-copy">
            <p className="lp-kicker lp-kicker-on-dark">LLM security gateway</p>
            <h1 id="landing-hero-title">
              Enforce policy between your app and any LLM
            </h1>
            <p className="lp-hero-lead">
              AEGIS is an open-source enforcer/gateway: CEL policy-as-code, human
              approval for high-risk tool calls, and Ed25519 audit trails —
              sitting between your application and whatever model provider you
              use.
            </p>
            <div className="lp-cta-row">
              <a
                className="btn-primary btn-lg lp-cta-primary"
                href="https://github.com/hamidmatiny/aegis"
                target="_blank"
                rel="noopener noreferrer"
              >
                View on GitHub
              </a>
              <a className="btn-secondary btn-lg lp-cta-ghost" href="#how-it-works">
                See interception
              </a>
            </div>
            <p className="lp-hero-note">
              Self-host: clone and run <code>./scripts/demo.sh</code>
            </p>
          </div>
          <aside className="lp-hero-aside" aria-label="Gateway path overview">
            <div className="lp-hero-diagram">
              <div className="lp-hd-node">App</div>
              <div className="lp-hd-arrow" aria-hidden="true" />
              <div className="lp-hd-node lp-hd-core">AEGIS</div>
              <div className="lp-hd-arrow" aria-hidden="true" />
              <div className="lp-hd-node">Provider</div>
            </div>
            <p className="lp-hero-diagram-caption">
              Drop-in OpenAI-compatible base URL. Policy and audit on every hop.
            </p>
          </aside>
        </div>
      </section>

      <section className="lp-proof" aria-label="Credibility">
        <ul className="lp-proof-grid">
          {PROOF.map((p) => (
            <li key={p.label}>
              <a
                className="lp-proof-card"
                href={p.href}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="lp-proof-label">{p.label}</span>
                <span className="lp-proof-value">{p.value}</span>
                <span className="lp-proof-detail">{p.detail}</span>
              </a>
            </li>
          ))}
        </ul>
      </section>

      <div className="lp-body">
        <InterceptionDemo />

        <section className="lp-section" aria-labelledby="features-title">
          <h2 id="features-title">What you get</h2>
          <div className="lp-feature-grid">
            {FEATURES.map((f) => (
              <article key={f.title} className="lp-card">
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section
          id="applied-example"
          className="lp-section"
          aria-labelledby="applied-title"
        >
          <h2 id="applied-title">Applied example on this stack</h2>
          <p className="lp-lead">
            defenseaegis.org also hosts an advisory Q&amp;A surface built on the
            same policy and audit primitives — not the core product.
          </p>
          <div className="lp-feature-grid lp-feature-grid-2">
            <article className="lp-card">
              <h3>Infrastructure Q&amp;A</h3>
              <p>
                Plain-language questions grounded in an inventory you provide.
                Answers are advisory only — they do not change your systems.
              </p>
            </article>
            <article className="lp-card">
              <div className="lp-card-head">
                <h3>Guided walkthroughs</h3>
                <span className="lp-pill">Optional</span>
              </div>
              <p>
                Longer step-by-step remediation guidance ($29 CAD/mo). Same audit
                trail; still advisory — not autonomous action-taking.
              </p>
            </article>
          </div>
          <div className="lp-cta-row" style={{ marginTop: "1.25rem" }}>
            <Link className="btn-secondary" to="/register">
              Try the Q&amp;A example — free to start
            </Link>
          </div>
        </section>

        <section id="pricing" className="lp-section" aria-labelledby="pricing-title">
          <h2 id="pricing-title">Run it yourself</h2>
          <p className="lp-lead">
            The enforcer is free to self-host. There is no subscription for the
            gateway. The $29 CAD plan is only the hosted advisory Q&amp;A example
            on this site — a side surface, not the product price.
          </p>
          <div className="lp-pricing-grid">
            <article className="lp-card lp-price-card lp-price-featured">
              <h3>Self-host the gateway</h3>
              <p className="lp-price-line">
                <span className="lp-price-amount">$0</span>
              </p>
              <ul className="lp-price-list">
                <li>CEL policy, risk tiers, human gate, Ed25519 audit</li>
                <li>OpenAI-compatible base URL in front of your provider</li>
                <li>
                  You run it — clone and <code>./scripts/demo.sh</code>
                </li>
              </ul>
              <a
                className="btn-primary"
                href="https://github.com/hamidmatiny/aegis"
                target="_blank"
                rel="noopener noreferrer"
              >
                View on GitHub
              </a>
            </article>
            <article className="lp-card lp-price-card">
              <h3>Hosted Q&amp;A example</h3>
              <p className="lp-price-line">
                <span className="lp-price-amount">$29</span>
                <span className="lp-price-unit">CAD / month</span>
              </p>
              <ul className="lp-price-list">
                <li>Not the gateway price</li>
                <li>Free tier: advisory Q&amp;A on an inventory you provide</li>
                <li>Paid tier: guided walkthroughs, still advisory</li>
              </ul>
              <Link className="btn-secondary" to="/register">
                Try the Q&amp;A example
              </Link>
            </article>
          </div>
        </section>

        <section id="trust" className="lp-section" aria-labelledby="trust-title">
          <h2 id="trust-title">Privacy &amp; data handling</h2>
          <div className="lp-card lp-trust">
            <ul className="lp-trust-list">
              <li>
                Self-hosted gateway traffic stays on your infrastructure. The
                hosted Q&amp;A example stores the inventory and questions you
                submit so answers stay grounded.
              </li>
              <li>
                We never ask you to paste production passwords, API keys, or SSH
                private keys — and we do not store credentials of that kind.
              </li>
              <li>
                Q&amp;A answers are advisory only. They do not change your
                systems. Gateway allow/deny decisions and Q&amp;A usage are
                recorded with an Ed25519-signed audit trail.
              </li>
            </ul>
            <p className="lp-muted small">
              Full detail: <Link to="/privacy">Privacy Policy</Link> ·{" "}
              <Link to="/terms">Terms of Use</Link>
            </p>
          </div>
        </section>

        <section className="lp-section lp-oss" aria-labelledby="oss-title">
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

        <footer className="lp-footer">
          <div className="lp-footer-grid">
            <div>
              <p className="lp-footer-brand">AEGIS</p>
              <p className="lp-muted small">
                LLM security gateway — policy, audit, human gate.
              </p>
            </div>
            <nav className="lp-footer-nav" aria-label="Footer">
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
          <p className="lp-muted small lp-footer-copy">
            © {new Date().getFullYear()} AEGIS. Enforcer/gateway is open source;
            hosted Q&amp;A is advisory — not a substitute for a security
            assessment.
          </p>
        </footer>
      </div>
    </div>
  );
}
