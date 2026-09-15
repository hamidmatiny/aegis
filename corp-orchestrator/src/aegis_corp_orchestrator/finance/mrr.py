"""Shared MRR snapshot for pnl_analyst and corp_read_company_state.

Both tools must call this so they cannot report different numbers.

MRR = monthly-normalized Stripe **live-mode** price unit_amount × count of
non-test tenants (tier premium/paid) whose ``stripe_subscription_id`` is
independently confirmed active in Stripe live mode.

Never trust the local DB subscription id alone — that is how a test-mode
object was previously counted as real revenue.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from aegis_corp_orchestrator.config import settings
from aegis_corp_orchestrator.db.connection import get_pool
from aegis_smb_session.test_accounts import SQL_TENANT_NOT_TEST

logger = logging.getLogger(__name__)

# Subscription statuses that count as paying for headline MRR.
_PAYING_STATUSES = frozenset({"active", "trialing"})


def _fetch_standard_price() -> dict[str, Any]:
    """Read unit_amount + recurring interval from Stripe for STRIPE_PRICE_ID_STANDARD."""
    secret = settings.stripe_secret_key
    price_id = settings.stripe_price_id_standard
    if not secret or not price_id:
        return {
            "ok": False,
            "error": "stripe_not_configured",
            "detail": "STRIPE_SECRET_KEY and STRIPE_PRICE_ID_STANDARD required",
        }
    if not secret.startswith("sk_live_"):
        return {
            "ok": False,
            "error": "stripe_not_live_mode",
            "detail": "STRIPE_SECRET_KEY must be a live-mode key (sk_live_*) for headline MRR",
        }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                f"https://api.stripe.com/v1/prices/{price_id}",
                auth=(secret, ""),
            )
        data = resp.json()
        if resp.status_code >= 400:
            return {
                "ok": False,
                "error": "stripe_price_fetch_failed",
                "status_code": resp.status_code,
                "detail": data.get("error") or data,
            }
        if data.get("livemode") is False:
            return {
                "ok": False,
                "error": "stripe_price_not_live",
                "detail": f"price {price_id} is not livemode",
            }
        recurring = data.get("recurring") or {}
        return {
            "ok": True,
            "price_id": data.get("id") or price_id,
            "unit_amount": data.get("unit_amount"),
            "currency": (data.get("currency") or "").upper(),
            "interval": recurring.get("interval"),
            "interval_count": int(recurring.get("interval_count") or 1),
            "livemode": bool(data.get("livemode")),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("stripe price fetch failed: %s", exc)
        return {"ok": False, "error": "stripe_price_fetch_exception", "detail": str(exc)}


def _monthly_amount_cents(unit_amount: int, interval: str | None, interval_count: int) -> int:
    """Normalize Stripe price to monthly cents."""
    count = max(interval_count or 1, 1)
    if interval == "year":
        return int(round(unit_amount / (12 * count)))
    if interval == "week":
        return int(round(unit_amount * (52 / 12) / count))
    if interval == "day":
        return int(round(unit_amount * (365 / 12) / count))
    # month (default)
    return int(round(unit_amount / count))


def _candidate_paying_rows() -> dict[str, Any]:
    """DB candidates: paid/premium, real subscription id, not flagged test."""
    pool = get_pool()
    try:
        with pool.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT t.id::text, t.slug, c.email, c.stripe_subscription_id
                FROM tenants t
                JOIN customers c ON c.tenant_id = t.id
                WHERE lower(t.tier) IN ('premium', 'paid')
                  AND c.stripe_subscription_id IS NOT NULL
                  AND c.stripe_subscription_id <> ''
                  AND {SQL_TENANT_NOT_TEST}
                """
            ).fetchall()
        candidates = [
            {
                "tenant_id": r[0],
                "slug": r[1],
                "email": r[2],
                "stripe_subscription_id": r[3],
            }
            for r in rows
        ]
        return {"ok": True, "candidates": candidates}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "candidates": []}


def _verify_live_subscription(secret: str, subscription_id: str) -> dict[str, Any]:
    """Confirm subscription exists in live Stripe and is in a paying status."""
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                f"https://api.stripe.com/v1/subscriptions/{subscription_id}",
                auth=(secret, ""),
            )
        data = resp.json()
        if resp.status_code == 404:
            return {
                "ok": False,
                "reason": "not_found_in_live_stripe",
                "subscription_id": subscription_id,
            }
        if resp.status_code >= 400:
            return {
                "ok": False,
                "reason": "stripe_fetch_failed",
                "status_code": resp.status_code,
                "detail": data.get("error") or data,
            }
        if data.get("livemode") is not True:
            return {
                "ok": False,
                "reason": "not_livemode",
                "subscription_id": subscription_id,
                "livemode": data.get("livemode"),
            }
        status = str(data.get("status") or "")
        if status not in _PAYING_STATUSES:
            return {
                "ok": False,
                "reason": "not_paying_status",
                "subscription_id": subscription_id,
                "status": status,
            }
        return {
            "ok": True,
            "subscription_id": subscription_id,
            "status": status,
            "livemode": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "reason": "stripe_exception",
            "detail": str(exc),
            "subscription_id": subscription_id,
        }


def _paying_subscriber_count() -> dict[str, Any]:
    """Count only non-test tenants with live-mode-verified paying subscriptions."""
    secret = settings.stripe_secret_key
    if not secret:
        return {
            "ok": False,
            "error": "stripe_not_configured",
            "paying_subscribers": 0,
            "excluded_unverified": 0,
        }
    if not secret.startswith("sk_live_"):
        return {
            "ok": False,
            "error": "stripe_not_live_mode",
            "paying_subscribers": 0,
            "excluded_unverified": 0,
        }

    cand = _candidate_paying_rows()
    if not cand.get("ok"):
        return {
            "ok": False,
            "error": cand.get("error"),
            "paying_subscribers": 0,
            "excluded_unverified": 0,
        }

    verified = 0
    rejected: list[dict[str, Any]] = []
    for row in cand["candidates"]:
        check = _verify_live_subscription(secret, str(row["stripe_subscription_id"]))
        if check.get("ok"):
            verified += 1
        else:
            rejected.append(
                {
                    "slug": row.get("slug"),
                    "subscription_id": row.get("stripe_subscription_id"),
                    "reason": check.get("reason"),
                }
            )
            logger.warning(
                "MRR exclude tenant slug=%s sub=%s reason=%s",
                row.get("slug"),
                row.get("stripe_subscription_id"),
                check.get("reason"),
            )

    return {
        "ok": True,
        "paying_subscribers": verified,
        "db_candidates": len(cand["candidates"]),
        "excluded_unverified": len(rejected),
        "rejected_sample": rejected[:10],
    }


def get_mrr_snapshot() -> dict[str, Any]:
    """Single source of truth for corp finance MRR figures."""
    price = _fetch_standard_price()
    subs = _paying_subscriber_count()
    out: dict[str, Any] = {
        "source": "shared:aegis_corp_orchestrator.finance.mrr.get_mrr_snapshot",
        "price": price,
        "paying_subscribers": subs.get("paying_subscribers", 0),
        "paying_query_ok": bool(subs.get("ok")),
        "db_candidates": subs.get("db_candidates"),
        "excluded_unverified": subs.get("excluded_unverified"),
        "live_mode_verified": True,
        "test_accounts_excluded": True,
    }
    if subs.get("rejected_sample"):
        out["rejected_sample"] = subs["rejected_sample"]
    if not subs.get("ok"):
        out["paying_error"] = subs.get("error")
    if not price.get("ok"):
        out["mrr_usd"] = None
        out["mrr_display"] = None
        out["unavailable"] = True
        out["reason"] = price.get("error") or "stripe_price_unavailable"
        return out
    if price.get("unit_amount") is None:
        out["mrr_usd"] = None
        out["mrr_display"] = None
        out["unavailable"] = True
        out["reason"] = "price_missing_unit_amount"
        return out
    if not subs.get("ok"):
        out["mrr_usd"] = None
        out["mrr_display"] = None
        out["unavailable"] = True
        out["reason"] = subs.get("error") or "paying_query_failed"
        return out

    unit = int(price["unit_amount"])
    monthly_cents = _monthly_amount_cents(
        unit, price.get("interval"), int(price.get("interval_count") or 1)
    )
    n = int(subs.get("paying_subscribers") or 0)
    total_cents = monthly_cents * n
    currency = str(price.get("currency") or "USD")
    amount = total_cents / 100.0
    out.update(
        {
            "unavailable": False,
            "unit_amount_cents": unit,
            "monthly_unit_cents": monthly_cents,
            "mrr_cents": total_cents,
            "mrr_usd": amount,  # numeric; currency may be CAD — see currency field
            "currency": currency,
            "mrr_display": f"${amount:.2f} {currency}",
            "formula": (
                f"{n} live-verified paying subscribers × "
                f"${monthly_cents/100:.2f} {currency}/mo "
                f"(from live Stripe price {price.get('price_id')}; "
                f"test accounts excluded)"
            ),
        }
    )
    return out
