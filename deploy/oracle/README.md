# Public demo on Oracle Cloud Always Free

Runs the real defended chat path (gateway + input-defense + output-defense +
policy-engine + model-router + agent-gate + audit + postgres, all on
`mock-model` — no LLM API keys, no cost) behind a rate-limited, keyless
public proxy, so anyone can watch AEGIS block a prompt injection without
installing anything.

Oracle's Always Free tier (not a trial) comfortably fits the whole stack:
up to 4 ARM OCPUs / 24GB RAM, 10TB egress, free forever.

## 1. Provision the VM (you do this — account creation isn't something I do on your behalf)

1. Create an Oracle Cloud account at [cloud.oracle.com](https://cloud.oracle.com) (requires a credit card for identity verification; the Always Free resources below never bill).
2. Console → **Compute → Instances → Create Instance**.
3. Image: **Ubuntu 22.04** (or 24.04). Shape: **VM.Standard.A1.Flex** (Ampere) — 2 OCPU / 12GB RAM is plenty for this demo; you can use up to 4/24 if you want headroom.
4. Under **Networking**, use a new VCN with internet access (the wizard's default is fine).
5. Add your SSH public key (or let Oracle generate a keypair for you to download).
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

- Public (port 80, rate-limited to 6 req/min/IP): `/health` and `/v1/chat/completions` only, via `demo-proxy` (nginx).
- Not public: the dashboard, the real gateway port 8080, Postgres, and every other service — they're only reachable inside the Docker network. The real `AEGIS_API_KEYS` value never leaves the VM; nginx injects it server-side.

## Optional: put a domain + HTTPS in front later

Once this has a real audience, swap `demo-proxy` for Caddy with a domain
name for automatic HTTPS, or put the VM behind Cloudflare. Not needed for
an initial demo — plain HTTP to the VM's IP is fine to start.
