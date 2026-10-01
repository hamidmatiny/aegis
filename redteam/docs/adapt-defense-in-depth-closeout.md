# Reserved Adapt → defense-in-depth closeout

**Date:** 2026-09-17  
**Owners (Track B):** `aegis-agent-gate` (primary), `aegis-policy-engine` (co-own)  
**Status:** Closed for Phase 1 inherit — primary policy PR already on `main`.

## What this was

After adaptive red-team campaigns produced reserved Adapt bypasses, an offline classifier
(`redteam/scripts/audit_reserved_adapt_defense_in_depth.py`) mapped each bypass to whether
**real** harm would need a tool call and what `policy-engine/policies/default.yaml` would do.

Key product finding from that audit class:

- Most Adapt bypasses are **content-only** (model text is the compromise) — `agent-gate`
  risk tiers do not stop them; content detectors / continuous `redteam/` monitoring do.
- Cookie/session **exfil narratives** map to network tools (`http_get`). Under the old
  pack, MEDIUM catalog risk fell through to `settings.default_action: allow`.

## Decision log

| Item | Decision | Evidence |
|------|----------|----------|
| Escalate `http_get` (MEDIUM exfil) | **Done — merged** | [PR #42](https://github.com/hamidmatiny/aegis/pull/42) `policy/escalate-medium-http-get-exfil` |
| Ship audit script as CI gate | **No** | Needs regenerable JSONL; historical dump expected 508 rows at `/tmp/reserved_adapt_bypasses.jsonl` (gone). Soft-fail CLI kept for archival re-runs. |
| Keep classifier in-tree | **Yes (archival tooling)** | `--input` / `--expect-n` / `--out`; exit 2 if input missing, with pointer to #42 |
| Escalate all HIGH/MEDIUM by tier alone | **Not in this PR** | Would change enforcer UX broadly; track as backlog (see below) |

## Remaining backlog (not blocked on this closeout)

Named rules already cover some HIGH corp tools. Still **default-allow** unless a named rule matches:

- `write_file` (HIGH)
- `send_email`, `post_message`, `read_file`, `corp_http_get` (MEDIUM)

Open a **scoped** follow-up PR if the enforcer sell requires escalate-on-tier (not silent).

## How to re-run the classifier

```bash
# After regenerating reserved Adapt bypass JSONL:
python3 redteam/scripts/audit_reserved_adapt_defense_in_depth.py \
  --input /path/to/reserved_adapt_bypasses.jsonl \
  --expect-n 508 \
  --out /tmp/reserved_adapt_defense_in_depth.json
```

Without input, the script exits 2 and prints that it is not a CI gate.
