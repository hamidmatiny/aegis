# Security Policy

AEGIS is a security product — vulnerabilities in it are higher-severity than
in typical software, since they can undermine the defenses it's meant to
provide. Please report them responsibly.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, use [GitHub's private vulnerability reporting](https://github.com/hamidmatiny/aegis/security/advisories/new)
for this repository. Include:

- Affected service(s) (`gateway`, `input-defense`, `agent-gate`, etc.)
- Steps to reproduce, or a minimal PoC
- Impact (what an attacker could do, and against what deployment: default
  self-hosted config vs. hardened production config)

We aim to acknowledge valid reports within 5 business days. We will coordinate
remediation and disclosure with the reporter when contact details are provided.

The Oracle public demo also publishes this policy at `/security.html` and
machine-readable contact information at `/.well-known/security.txt`.

## Safe harbor

We support good-faith security research conducted under this policy. We will
not pursue legal action for research that avoids privacy violations, service
disruption, data destruction, and actions outside this scope. If you are
unsure whether a test is permitted, report the concern first and wait for
guidance.

## Scope

In scope: any of the services in this monorepo (`gateway`, `input-defense`,
`output-defense`, `policy-engine`, `model-router`, `agent-gate`, `audit`,
`redteam`, `dashboard`, `sdk/`), and the Docker/Helm deployment manifests
under `deploy/`.

Known, already-documented limitation: adaptive-attacker bypass rates against
the detection layer are tracked openly in [RESULTS.md](./RESULTS.md) — that
is expected, ongoing research, not something to report as a new finding
unless you have a *specific reproducible bypass* not already covered there.

Out of scope: denial-of-service testing, social engineering, physical attacks,
third-party services, and accessing, modifying, or deleting data that is not
your own.

## Supply chain

- Dependencies are scanned weekly via Dependabot and `govulncheck` /
  `pip-audit` / `npm audit` (see `.github/workflows/security.yml`).
- Released container images are signed keylessly with
  [cosign](https://github.com/sigstore/cosign) via GitHub OIDC and shipped
  with a CycloneDX SBOM (see `.github/workflows/release.yml`). Verify with:

  ```bash
  cosign verify \
    --certificate-identity-regexp "https://github.com/hamidmatiny/aegis/.*" \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    ghcr.io/hamidmatiny/aegis-gateway:latest
  ```
