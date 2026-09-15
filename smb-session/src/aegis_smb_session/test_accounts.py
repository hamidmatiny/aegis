"""Classify test/QA/automation accounts so they never inflate headline metrics.

Used by smb-copilot (set ``tenants.is_test_account`` at creation) and
corp-orchestrator's BEV/MRR path (exclude flagged rows). Patterns below are
the documented historical classifier from the 2026-09 fact-check — review
before extending; do not silently invent new ones.
"""

from __future__ import annotations

import os
from typing import Iterable

# --- Documented historical email patterns (investigation 2026-09) ---
EMAIL_DOMAIN_SUFFIXES: tuple[str, ...] = (
    "@example.com",
    "@example.test",
)

EMAIL_LOCAL_PREFIXES: tuple[str, ...] = (
    "e2e-",
    "e2e-so-",
    "stripe-e2e-",
    "stripe-check-",
    "live-verify-",
    "ask-check-",
    "logout-check-",
    "logout-fix+",
    "avatar-diag+",
    "landing-checkout+",
    "landing-smoke+",
    "mock",
    "live0",
    "prod-ask-",
    "live-avatar-",
)

# --- Documented historical slug prefixes ---
SLUG_PREFIXES: tuple[str, ...] = (
    "stripe-e2e-",
    "stripe-check-",
    "live-verify-",
    "mock",
    "live0",
    "prod-ask-",
    "live-avatar-",
    "e2e-",
    "e2e-so-",
    "navtest-",
    "navptest-",
    "ask-",
    "logout-",
    "avatar-diag-",
    "ui-chk-",
    "ui-reg-",
    "ui-guest-",
    "dbg-guest-",
    "api-reg-",
    "landing-smoke-",
)

# SQL predicate fragments (Postgres). Keep in sync with classify_test_account().
SQL_TENANT_NOT_TEST = "NOT COALESCE(t.is_test_account, FALSE)"
SQL_TENANTS_NOT_TEST = "NOT COALESCE(is_test_account, FALSE)"


def _internal_emails() -> set[str]:
    """Owner/operator accounts that must not count as organic customers.

    Set ``AEGIS_INTERNAL_ACCOUNT_EMAILS`` to a comma-separated list (lowercased).
    Empty by default — populate on the host with Hamid's known personal emails
    rather than hardcoding PII into the repo.
    """
    raw = os.environ.get("AEGIS_INTERNAL_ACCOUNT_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def classify_test_account(
    *,
    email: str | None = None,
    slug: str | None = None,
    force: bool = False,
) -> bool:
    """Return True if this account must be excluded from headline MRR/signups."""
    if force:
        return True
    if os.environ.get("AEGIS_FORCE_TEST_ACCOUNTS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return True

    email_n = (email or "").strip().lower()
    slug_n = (slug or "").strip().lower()

    if email_n and email_n in _internal_emails():
        return True

    if email_n:
        for suffix in EMAIL_DOMAIN_SUFFIXES:
            if email_n.endswith(suffix):
                return True
        local = email_n.split("@", 1)[0]
        for prefix in EMAIL_LOCAL_PREFIXES:
            if local.startswith(prefix) or email_n.startswith(prefix):
                return True

    if slug_n:
        for prefix in SLUG_PREFIXES:
            if slug_n.startswith(prefix):
                return True

    return False


def backfill_sql_predicates() -> list[str]:
    """SQL OR clauses used by the one-shot historical backfill migration."""
    clauses: list[str] = []
    for suffix in EMAIL_DOMAIN_SUFFIXES:
        # escape single quotes for SQL string literals
        s = suffix.replace("'", "''")
        clauses.append(f"lower(c.email) LIKE '%{s}'")
    for prefix in EMAIL_LOCAL_PREFIXES:
        p = prefix.replace("'", "''")
        clauses.append(f"lower(c.email) LIKE '{p}%'")
    for prefix in SLUG_PREFIXES:
        p = prefix.replace("'", "''")
        clauses.append(f"lower(t.slug) LIKE '{p}%'")
    return clauses


def documented_patterns() -> dict[str, Iterable[str]]:
    """Public description of patterns for operators / READMEs."""
    return {
        "email_domain_suffixes": EMAIL_DOMAIN_SUFFIXES,
        "email_local_prefixes": EMAIL_LOCAL_PREFIXES,
        "slug_prefixes": SLUG_PREFIXES,
        "internal_emails_env": "AEGIS_INTERNAL_ACCOUNT_EMAILS",
        "force_env": "AEGIS_FORCE_TEST_ACCOUNTS",
    }
