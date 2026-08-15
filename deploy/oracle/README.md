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

`setup.sh` actually picks between three profiles based on detected RAM:

| Total RAM | Profile | Detectors |
|---|---|---|
| < 2GB (`E2.1.Micro`) | `docker-compose.demo-lite.yml` | stub/regex — real transformer models can't fit |
| 2GB – <6GB | none (base compose) | stub/regex — the *default*, even though there'd be room to run the full stack; real models still don't comfortably fit alongside everything else |
| ≥ 6GB (`A1.Flex`, sized up) | `docker-compose.demo-ml.yml` | **real models**: Llama-Prompt-Guard-2 + a perplexity LM (input-defense), Toxic-BERT + spaCy NER (output-defense) |

If you want the real-model profile, request at least **2 OCPU / 8GB** (not
the minimal 12GB default suggested below — 8GB clears the 6GB bar with
headroom) when creating the `A1.Flex` instance. The first `up` after
switching profiles downloads ~1.5GB of model weights, so expect it to take
several minutes longer than a normal redeploy. See
[`input-defense/README.md`](../../input-defense/README.md#model-footprint)
and [`output-defense/README.md`](../../output-defense/README.md) for the
exact per-model footprint this budget is based on.

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

## Detecting rogue-agent tool use (ASI10)

Every `TOOL_GATE` decision agent-gate makes gets an audit receipt carrying
`tool_name` and `agent_id` (added in Phase 3.1). `audit` doesn't expose a
query filter for either field, and it's bound to `127.0.0.1` only (see
above), so detection runs on the box itself:

```bash
cd aegis
set -a; source .env; set +a   # loads AEGIS_INTERNAL_TOKEN -- audit rejects unauthenticated requests now
python3 scripts/asi10-rogue-agent-query.py
```

It fetches TOOL_GATE receipts and flags, per `agent_id`, the first time it
calls a `tool_name` outside tools it's already used before -- a simple
"this agent just reached for something new" signal. Exit code is `1` if
it found anything, `0` if clean, so it's cron-friendly:

```bash
# Daily at 07:00, mail on any anomaly (crontab -e on the VM). cron doesn't
# source .env, so export the token inline or via crontab's own env line.
0 7 * * * cd ~/aegis && export $(grep AEGIS_INTERNAL_TOKEN .env) && python3 scripts/asi10-rogue-agent-query.py --since 24h
```

Run `python3 scripts/asi10-rogue-agent-query.py --help` for `--tenant-id`,
`--agent-id`, `--json`, and other flags.

## Detecting agent-identity inconsistencies (ASI07)

`agent_id` is entirely caller-declared -- agent-gate's auth is a shared
service-key set, not a per-agent credential, so nothing stops one key
from claiming a different agent's identity. Since Stage E.2, every
`TOOL_GATE` receipt also carries `service_key_fingerprint` (a short,
non-reversible hash of whichever key authenticated the request), so this
can be cross-checked after the fact:

```bash
cd aegis
set -a; source .env; set +a
python3 scripts/asi07-identity-consistency-query.py
```

It flags the first time an established `agent_id` shows up under a NEW
key fingerprint (could be a legitimate credential rotation, could be
someone else claiming that identity -- investigate, don't assume). It
also prints, purely informationally, how many distinct `agent_id` values
each key has claimed -- this repo's own examples legitimately share one
key across several agent_ids, so that's not flagged as an anomaly unless
you pass `--max-agents-per-key` for a deployment that provisions one key
per agent and wants that assumption enforced. Same cron-friendly exit
code contract as the ASI10 script above (`1` on any anomaly, `0` clean):

```bash
0 7 * * * cd ~/aegis && export $(grep AEGIS_INTERNAL_TOKEN .env) && python3 scripts/asi07-identity-consistency-query.py --since 24h
```

This is a detection signal, not enforcement -- agent-gate does not block
on any of this. True per-agent enforcement would need real per-agent
credentials, a bigger architecture change than this phase; see the
script's own module docstring for the full reasoning.

## Recovering credentials if this box is lost

`./scripts/generate-credentials.sh` generates everything into `.env`,
which only ever exists on this box — losing it means losing every
credential with no history (and `POSTGRES_PASSWORD` rotation on an
already-running database needs a manual `ALTER USER` step, so this isn't
a purely cosmetic problem). If you've set up the optional SOPS+age backup
(see [.sops.yaml](../../.sops.yaml) in the repo root), recovery on a
fresh box is:

```bash
git clone https://github.com/hamidmatiny/aegis.git
cd aegis
export SOPS_AGE_KEY_FILE=/path/to/your/age-key.txt   # never committed, kept by you
./scripts/decrypt-credentials.sh
./deploy/oracle/setup.sh
```

`setup.sh` itself also checks for `.env.enc` + an available age key before
generating fresh credentials, so this can also happen automatically as
part of a normal `setup.sh` run on a fresh box.

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
