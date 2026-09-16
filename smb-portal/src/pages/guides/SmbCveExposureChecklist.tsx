import { Link } from "react-router-dom";

/** Published by aegis-growth — SMB CVE exposure checklist (SEO guide). */
export function SmbCveExposureChecklist() {
  return (
    <section className="page legal-page">
      <header className="page-hero">
        <h1>How to check if your small-business servers are exposed to a new CVE</h1>
        <p className="muted">
          Published: 2026-09-16 · Target query: how to check CVE exposure small
          business server · By AEGIS Growth
        </p>
      </header>
      <div className="panel stack legal-body">
        <p>
          You do not need a Fortune-500 security team to react to a CVE. You need
          three facts: (1) what software you actually run, (2) whether that CVE
          applies to your versions, and (3) what to do in the next 24–72 hours if
          it does. Most “urgent” headlines do not apply to a typical five-person
          company running a single VPS, Postgres, and a reverse proxy — but some
          do, and those are the ones that matter.
        </p>

        <h2>Step 1 — Inventory what you run (30 minutes)</h2>
        <p>Write down, for each server or SaaS dependency:</p>
        <ul>
          <li>OS and major version</li>
          <li>Database (e.g. Postgres) and version</li>
          <li>Web proxy (nginx, Caddy, etc.)</li>
          <li>Container runtime (Docker / Compose) if used</li>
          <li>Identity provider / SSO if any</li>
          <li>
            Anything internet-facing (VPN, admin panels, WordPress, etc.)
          </li>
        </ul>
        <p>
          If you cannot list it, you cannot match a CVE to it. A simple
          spreadsheet beats an unread SIEM.
        </p>

        <h2>Step 2 — Read the CVE like an adult</h2>
        <p>For each new CVE in the news:</p>
        <ol>
          <li>
            <strong>Affected product and versions</strong> — if you do not run
            it, stop.
          </li>
          <li>
            <strong>Attack prerequisites</strong> — does the attacker need to
            already be on your network? Unauthenticated remote? Admin
            credentials?
          </li>
          <li>
            <strong>Fixed version</strong> — is there a patch you can actually
            install this week?
          </li>
        </ol>
        <p>
          Ignore CVSS theater until those three are clear. A “critical” score on
          software you do not run is noise.
        </p>

        <h2>Step 3 — Match, then act</h2>
        <ul>
          <li>
            <strong>No matching software</strong> — log “reviewed, N/A” and move
            on.
          </li>
          <li>
            <strong>Matching software, not internet-exposed, patch available</strong>{" "}
            — schedule update in your normal window.
          </li>
          <li>
            <strong>Matching + internet-exposed + exploit chatter</strong> —
            patch or mitigate within 24–72 hours; restrict exposure (firewall,
            disable feature) until then.
          </li>
          <li>
            <strong>Matching, no patch yet</strong> — mitigate: network restrict,
            feature flag off, WAF rule if you have one; watch vendor advisory.
          </li>
        </ul>

        <h2>Step 4 — Where AEGIS fits</h2>
        <p>
          AEGIS-for-SMB (
          <a href="https://defenseaegis.org">defenseaegis.org</a>) helps small
          teams ask plain-language infrastructure and CVE questions against a
          real stack profile — guided walkthroughs rather than raw NVD dumps. It
          does not replace patching your own servers. Use it to shorten the
          “does this apply to me?” loop; then patch on your host.
        </p>

        <h2>Common SMB mistakes</h2>
        <ul>
          <li>Panic-upgrading everything because social media said “critical”</li>
          <li>Ignoring a boring CVE on an internet-facing admin panel</li>
          <li>Having no inventory, so every headline feels personal</li>
          <li>Paying for a tool before you can name your Postgres version</li>
        </ul>

        <h2>Checklist you can reuse</h2>
        <ul>
          <li>Inventory current versions</li>
          <li>Confirm whether the CVE’s product is on that list</li>
          <li>Confirm exposure (public / private)</li>
          <li>Apply patch or temporary mitigation</li>
          <li>Record the decision date</li>
        </ul>

        <p className="muted">
          Organic SEO note: one guide will not move revenue overnight — this is a
          weeks-to-months channel.{" "}
          <Link to="/">Back to AEGIS</Link> ·{" "}
          <Link to="/onboarding">Try the product</Link>
        </p>
      </div>
    </section>
  );
}
