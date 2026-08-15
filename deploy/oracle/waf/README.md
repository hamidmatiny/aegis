# Self-hosted WAF scaffold (Stage C.2) — dormant, not wired in

This is a **built and testable, but not running** alternative/complement to
Cloudflare's proxy (Stage C.1). It exists so the option is ready to switch
on later — e.g. after an Oracle RAM upgrade — without starting from
scratch. As of this writing, **Cloudflare's free proxy tier is the actual,
live protection for defenseaegis.org.** Nothing in this document changes
that; `setup.sh` never references `docker-compose.waf.yml`.

## Why this exists alongside Cloudflare, not instead of it

Cloudflare's proxy costs zero extra RAM on the 1GB Oracle box (`aegis-demo-v2`)
and covers most of the same ground — TLS termination, basic bot/DDoS
mitigation. Coraza + CrowdSec together are a genuine, capable self-hosted
alternative, but they cost real memory (roughly 150-200MB combined, per the
research behind the original security roadmap) that this box can't
comfortably spare on top of the full AEGIS stack. If Cloudflare's terms,
pricing, or availability ever stop working for this project, or the box
gets more RAM and self-hosting becomes attractive for its own sake (no
third-party in the request path at all), this is what gets wired in
instead — without having to design it from zero at that point.

## What's actually in `docker-compose.waf.yml`

Two containers, both from actively-maintained upstream projects, neither
built from source in this repo:

1. **`coraza-waf`** — [`ghcr.io/coreruleset/coraza-crs`](https://github.com/coreruleset/coraza-crs-docker),
   the official Docker packaging of the OWASP Coraza WAF engine plus the
   OWASP Core Rule Set (CRS) v4. This is the actual line-of-defense
   component: it inspects HTTP requests for SQL injection, XSS, path
   traversal, and other CRS-covered attack signatures. Configured to sit
   in front of `demo-proxy` (`BACKEND=demo-proxy:80`) — `demo-proxy` keeps
   doing exactly what it does today (API key injection, rate limiting,
   canary redirects); Coraza's only job is filtering before traffic ever
   reaches it. Nothing about `demo-proxy` or `nginx-demo.conf.template`
   changes.

2. **`crowdsec`** — the official `crowdsecurity/crowdsec` image, running
   the `crowdsecurity/nginx` collection (community-maintained parsers +
   behavioral scenarios: crawling, probing, bad user agents, SQLi/XSS
   probing patterns that don't necessarily trip a single CRS rule but look
   automated/malicious across a sequence of requests). It tails Coraza's
   access log (shared via the `coraza-access-log` volume) and makes ban
   decisions available over its own Local API. **On its own, this
   container does not block anything** — it only detects and records.

## The piece that's deliberately not in this file: the firewall bouncer

Turning CrowdSec's decisions into actual blocked traffic needs a
**bouncer** — a small daemon that watches the Local API and inserts
`iptables`/`nftables` rules. As of this writing, CrowdSec does not publish
an official Docker image for `cs-firewall-bouncer`; the officially
documented install path is a host-level systemd package
(`crowdsec-firewall-bouncer-iptables` via CrowdSec's own apt/yum repo),
because it needs direct access to the host's netfilter tables — a
Compose-only design would either not work correctly or require pulling in
an unofficial third-party container image with `NET_ADMIN`/`NET_RAW`
capabilities, which isn't a trade worth making for a *security* project.
This is a deliberate, disclosed gap in this scaffold, not an oversight —
see "Activating this for real" below for the actual host-level step.

## Testing/inspecting this without going live

```bash
cd aegis
docker compose -f docker-compose.yml -f deploy/oracle/docker-compose.demo.yml -f deploy/oracle/docker-compose.waf.yml up -d coraza-waf crowdsec
```

This starts Coraza and CrowdSec alongside your already-running stack,
without touching `demo-proxy`'s ports (80/443 stay exactly as they are —
Coraza listens on `127.0.0.1:8081` only, not reachable from outside the
box). Try a request that should trip a CRS rule:

```bash
curl -i "http://localhost:8081/?id=1%20AND%201=1"
```

`CORAZA_RULE_ENGINE` is set to `DetectionOnly` in this overlay on purpose
— even running it this way, it logs what it *would* block rather than
actually blocking, a second layer of caution on top of this file simply
never being in `setup.sh`'s compose chain. Check what it saw:

```bash
docker compose logs coraza-waf | tail -50
docker compose exec crowdsec cscli metrics
docker compose exec crowdsec cscli alerts list
```

Tear down with:

```bash
docker compose -f docker-compose.yml -f deploy/oracle/docker-compose.demo.yml -f deploy/oracle/docker-compose.waf.yml down
```

## Activating this for real (not done, this is future reference)

1. Install the firewall bouncer on the host (the real enforcement piece,
   per the gap disclosed above): follow
   [CrowdSec's own installation docs](https://docs.crowdsec.net/u/bouncers/firewall/)
   for `crowdsec-firewall-bouncer-iptables`, pointing its `api_url` at
   this container's Local API (`http://<host>:8080` by default) and an
   API key generated via `docker compose exec crowdsec cscli bouncers add <name>`.
   Configure it to act on the `DOCKER-USER` iptables chain specifically —
   the chain Docker itself creates for exactly this purpose, so bans don't
   interfere with Docker's own port-forwarding rules.
2. Flip `CORAZA_RULE_ENGINE` from `DetectionOnly` to `On` in
   `docker-compose.waf.yml`, only after watching it run against real
   traffic long enough to be confident it isn't blocking anything
   legitimate.
3. Remove `demo-proxy`'s `80:80`/`443:443` port mappings from
   `deploy/oracle/docker-compose.demo.yml`, and give `coraza-waf` those
   same host ports instead (it becomes the new outermost layer).
4. Add `-f deploy/oracle/docker-compose.waf.yml` to the appropriate
   `COMPOSE_FILES` array in `deploy/oracle/setup.sh`, alongside
   `coraza-waf`/`crowdsec` in the `docker compose up` service list.
5. Decide how this interacts with Cloudflare (Stage C.1) — running both
   at once is possible (Cloudflare proxying to this box's own WAF) but is
   redundant defense-in-depth, not obviously worth the RAM cost;
   dropping Cloudflare's proxy (DNS-only / grey-cloud) and relying on this
   instead is the more likely real choice if this ever gets activated.

None of this is done by this patch. This section exists so future-you (or
whoever picks this up) isn't starting from a blank page.
