# Disaster recovery runbook

This is the authoritative DR procedure for the deployed AEGIS instance. It is
scoped to what this deployment actually is: a single, solo-operated Oracle
Cloud VM (see `deploy/oracle/README.md`), not a multi-region service with a
real point-in-time-recovery requirement. Everything here is sized to that
reality on purpose -- see "What this deliberately does not do" at the end.

## What's actually at risk

`docker-compose.yml` has exactly one persistent volume: `postgres_data`.
Everything else the stack needs is reproducible from elsewhere and is not a
backup concern:

| Data | Where it really lives | Lost if the VM disappears? |
|---|---|---|
| Source code, policy packs (`policy-engine/policies/`), Dockerfiles, compose files | GitHub (`github.com/hamidmatiny/aegis`) | No -- `git clone` recovers it |
| Container images | GHCR (`ghcr.io/hamidmatiny/aegis-*`), built by `.github/workflows/release.yml` | No -- `docker compose pull` recovers them |
| Credentials (`.env`) | The VM's disk only, unless backed up | Yes, unless restored from `.env.enc` -- see Stage B.1 / `.sops.yaml` |
| `audit_receipts` (the signed audit trail) | `postgres_data` on the VM only | Yes, unless restored from a postgres backup -- this document |
| `attack_patterns` (redteam's learned adaptive-attack corpus) | `postgres_data` on the VM only | Yes, unless restored from a postgres backup -- this document |
| Redis | In-memory only, no volume (`read_only: true`, `tmpfs: [/tmp]`) | Yes, always, on every restart -- by design, it's a cache, not a store |

So the entire DR problem this document solves is: **back up `postgres_data`,
and know how to restore it** -- everything else already has a durable copy
somewhere that isn't this one VM.

## The backup mechanism

`scripts/backup-postgres.sh` runs `pg_dump` against the live database,
gzips it, and -- reusing Stage B.1's existing SOPS+age setup rather than
inventing a second secrets mechanism -- encrypts it to
`backups/postgres-latest.sql.gz.enc` using the same age recipient already
configured in `.sops.yaml` for `.env.enc`.

It is deliberately a single **overwritten** snapshot, not a growing history.
At this project's actual scale that's the right tradeoff: no unbounded disk
growth, no retention policy to maintain, and a single well-known file to
reason about. If you later want point-in-time recovery across multiple
snapshots, that's a real future upgrade, not something silently missing --
it's just not needed yet.

`deploy/oracle/setup.sh` installs this as a daily cron job (03:00 box time)
automatically, idempotently (safe to re-run `setup.sh` after every
`git pull` without accumulating duplicate cron entries). Logs go to
`backups/backup.log`. To change the schedule, edit the box's crontab
directly (`crontab -e`) -- `setup.sh` won't fight you on it as long as the
line still contains `scripts/backup-postgres.sh` somewhere for its own
dedupe check to find.

## The one real single point of failure: the age private key

The age private key (generated once via `age-keygen`, per `.sops.yaml`'s
setup instructions) lives **only on your Mac** -- never on the Oracle box,
never committed to the repo, by design (see N51/N52 in the project history:
this design choice is exactly what contained a real leaked-key incident
without a repo history rewrite). That's correct for protecting the box, but
it means: **if you lose that key, both `.env.enc` and every
`postgres-latest.sql.gz.enc` become permanently undecryptable**, even though
the ciphertext itself is safely sitting in git.

This document isn't prescribing where to keep a second copy (a password
manager entry, a printed copy in a safe, whatever you're actually going to
maintain) -- just flagging clearly that this key is the one thing in this
entire DR story that has no backup of its own, and that's worth fixing in
whatever way you'll actually keep up with.

## Off-box redundancy is a manual step, on purpose

The daily cron job backs up `postgres_data` to a file **on the same VM**.
That protects against operator error or data corruption on a live box, but
**not** against losing the VM entirely -- if the box is gone, the backup file
on its disk is gone with it.

This script deliberately does **not** `git add`/`commit`/`push` the
encrypted backup automatically. Doing that would require a git-push-capable
credential living unattended on a public-facing box -- exactly the class of
risk this project has already been burned by once (the leaked SOPS age key,
N51/N52, and two separately leaked GitHub PATs earlier in this project's
history). A cron job quietly holding push access is a bigger new risk than
the DR gap it would close.

Instead, periodically do one of these yourself:

- `git add backups/postgres-latest.sql.gz.enc && git commit -m "backup: postgres snapshot" && git push`
  from the box (or `scp` the file to your Mac first and commit it from
  there) -- mirrors exactly how `.env.enc` already gets committed.
- Or just `scp ubuntu@<vm-ip>:~/aegis/backups/postgres-latest.sql.gz.enc ./` to your Mac
  periodically, no git involved.

Whichever you pick, do it before anything risky (a schema change, a
migration, a redeploy you're unsure about) and on some regular cadence
otherwise. Your actual RPO for a *total VM loss* is however long it's been
since your last manual off-box copy -- not the daily cron interval, which
only protects you if the VM itself survives.

## Scenario 1: total VM loss

This has actually happened once already (see N37 in the project history --
lost SSH access to the original box, recovered by provisioning a fresh
replacement). The same procedure applies here, with the postgres restore
step added:

1. Provision a new VM (same shape is fine -- `deploy/oracle/README.md` has
   sizing notes). Confirm SSH access **immediately** after creation, before
   doing anything else (the lesson from N37: assuming it worked is how the
   original box's problem went undetected for so long).
2. `git clone https://github.com/hamidmatiny/aegis.git && cd aegis`
3. Restore credentials: get the age private key onto the new box (from
   wherever you kept your second copy, or copy it over from your Mac),
   `export SOPS_AGE_KEY_FILE=/path/to/age-key.txt`, then
   `./scripts/decrypt-credentials.sh`. If you don't have `.env.enc` in the
   fresh checkout (it wasn't committed since the last change) or don't have
   the key, `./deploy/oracle/setup.sh` will generate fresh credentials
   instead -- fine for most values, but see the `POSTGRES_PASSWORD`/
   `AEGIS_AUDIT_SIGNING_KEY` caveats in `scripts/generate-credentials.sh` if
   you're also restoring postgres data signed/protected under the *old*
   credentials.
4. `./deploy/oracle/setup.sh` -- brings up the stack, installs the new
   backup cron job.
5. Restore postgres data, if you have an off-box copy of the encrypted
   dump (see "Off-box redundancy" above -- without one, this step is
   skipped and `audit_receipts`/`attack_patterns` start empty on the new
   box, which is a real, disclosed data loss, not silently glossed over):
   ```
   scp your-mac:/path/to/postgres-latest.sql.gz.enc ./backups/
   ./scripts/restore-postgres.sh
   ```

## Scenario 2: postgres data corrupted or accidentally wiped, box otherwise fine

```
./scripts/restore-postgres.sh
```
Restores from this box's own `backups/postgres-latest.sql.gz.enc` (the most
recent cron run). RPO here is bounded by the cron schedule -- up to ~24h of
data since the last run, by default.

## Scenario 3: credentials lost, box otherwise fine

Already covered by Stage B.1 -- see `scripts/decrypt-credentials.sh` and
`.sops.yaml`. Not duplicated here.

## RTO / RPO summary

| Scenario | RTO (time to recover) | RPO (data loss window) |
|---|---|---|
| Postgres corrupted, box fine | Minutes (one `restore-postgres.sh` run) | Up to ~24h (daily cron) |
| Credentials lost, box fine | Minutes (`decrypt-credentials.sh`) | None (credentials don't change on their own) |
| Total VM loss, off-box postgres copy exists | Under a day (proven by N37's real recovery) | Since your last manual off-box copy |
| Total VM loss, no off-box postgres copy | Under a day for the service itself; `audit_receipts`/`attack_patterns` data loss is total | N/A -- data is gone |

## What this deliberately does not do

No automated offsite replication, no multi-region failover, no backup
retention policy beyond "the latest one," no automatic git-push from the
box. All of that is real engineering for a service with paying users and an
SLA -- this is a solo-operated demo/OSS project on a single Always Free VM,
and matching effort to actual stakes is a standing principle for this
project (see the security roadmap's own "no Kubernetes, no SIEM, don't chase
every gap at once" stance). If usage or stakes change, this is the first
document to revisit.

## Verification

This has not yet been tested against a real `pg_dump`/`sops` round trip end
to end (no Docker daemon or real `sops`/`age` binaries were available in the
environment this was authored in -- see the accompanying delivery notes).
Before trusting this for a real incident:

```
./scripts/backup-postgres.sh
./scripts/restore-postgres.sh --force   # into the same, already-populated DB, as a dry run
```
and confirm row counts in `audit_receipts`/`attack_patterns` match before
and after. Worth re-running this drill periodically (quarterly is a
reasonable cadence for a project this size), not just once.
