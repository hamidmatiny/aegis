# Public demo on Oracle Cloud Always Free

Runs the real defended chat path (gateway + input-defense + output-defense +
policy-engine + model-router + agent-gate + audit + postgres, all on
`mock-model` — no LLM API keys, no cost) behind a rate-limited, keyless
public proxy, so anyone can watch AEGIS block a prompt injection without
installing anything.

## Which shape you'll actually get

**`VM.Standard.A1.Flex`** (Ampere, up to 4 OCPU / 24GB RAM) is the shape to
prefer — comfortably fits the whole stack with no trimming. In practice,
Oracle frequently reports **"Out of capacity"** for this shape depending on
region and timing; it's a known, common Always Free limitation, not
anything wrong with your account. Retrying occasionally (it can clear in
minutes or take days) is the only real fix short of a scripted retry loop.

**`VM.Standard.E2.1.Micro`** (AMD, 1 OCPU / 1GB RAM) is reliably available
and works fine as a fallback — `setup.sh` **auto-detects** low memory and
switches to a trimmed profile (`docker-compose.demo-lite.yml`): every
ML-capable detector forced onto its lightweight stub backend, every
container memory-capped, plus a 2GB swap file as a safety net. You don't
need to do anything differently — same `./deploy/oracle/setup.sh` command
either way.

## 1. Provision the VM (you do this — account creation isn't something I do on your behalf)

1. Create an Oracle Cloud account at [cloud.oracle.com](https://cloud.oracle.com) (requires a credit card for identity verification; the Always Free resources below never bill).
2. Console → **Compute → Instances → Create Instance**.
3. Image: **Ubuntu 22.04** (or 24.04). Shape: try **VM.Standard.A1.Flex** first (Ampere tab in the shape browser — it won't show under "Specialty and previous generation"), 2 OCPU / 12GB RAM. If you hit "Out of capacity," fall back to **VM.Standard.E2.1.Micro** — same deploy script handles both.
4. Under **Networking**, use a new VCN with internet access (the wizard's default is fine) — or reuse an existing VCN if you already opened port 80 on one.
5. Add your SSH public key (generate one first if needed: `ssh-keygen -t ed25519 -f ~/.ssh/aegis_oracle`), or let Oracle generate a keypair for you to download.
6. Create the instance and note its **public IP**.

## 2. Open port 80

Two firewalls to open — people miss the second one and then can't figure out why the demo isn't reachable:

1. **OCI Security List / NSG**: your instance's subnet → Security List → Add Ingress Rule → source `0.0.0.0/0`, TCP, destination port `80`.
2. **The VM's own iptables**: Oracle's Ubuntu images ship with restrictive rules by default. `deploy/oracle/setup.sh` (below) opens this for you automatically.

## 3. Deploy

SSH into the VM, then:

```bash
git clone https://github.com/hamidmatiny/aegis.git
cd aegis
./deploy/oracle/setup.sh
```

The script installs Docker, opens the local firewall, generates credentials,
starts the stack, and prints the public curl commands to try.

## 4. Redeploying after changes

```bash
cd aegis
git pull
./deploy/oracle/setup.sh
```

Safe to re-run — it reuses your existing `.env` credentials and just rebuilds/restarts.

## What's exposed vs. what isn't

- Public (port 80, rate-limited to 6 req/min/IP): a browser demo page at `/` (`deploy/oracle/demo-web/index.html` — a text box, a few example prompts, and a live verdict/score display), plus the underlying `/health` and `/v1/chat/completions` routes it calls, via `demo-proxy` (nginx).
- Not public: the dashboard, the real gateway port 8080, Postgres, and every other service — they're only reachable inside the Docker network. The real `AEGIS_API_KEYS` value never leaves the VM; nginx injects it server-side.

## Updating just the webpage

Edit `deploy/oracle/demo-web/index.html`, commit, push, then on the VM:

```bash
cd aegis && git pull && ./deploy/oracle/setup.sh
```

`setup.sh` remounts the volume and restarts `demo-proxy`, so page-only
changes redeploy in seconds even though the full script re-runs.

## Optional: put a domain + HTTPS in front later

Once this has a real audience, swap `demo-proxy` for Caddy with a domain
name for automatic HTTPS, or put the VM behind Cloudflare. Not needed for
an initial demo — plain HTTP to the VM's IP is fine to start.
