"""Shared MRR snapshot for pnl_analyst and corp_read_company_state.

Both tools must call this so they cannot report different numbers.
MRR = monthly-normalized Stripe price unit_amount × count of paying
tenants (tier premium/paid) with a real stripe_subscription_id.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from aegis_corp_orchestrator.config import settings
from aegis_corp_orchestrator.db.connection import get_pool

logger = logging.getLogger(__name__)


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
        recurring = data.get("recurring") or {}
        return {
            "ok": True,
            "price_id": data.get("id") or price_id,
            "unit_amount": data.get("unit_amount"),
            "currency": (data.get("currency") or "").upper(),
            "interval": recurring.get("interval"),
            "interval_count": int(recurring.get("interval_count") or 1),
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


def _paying_subscriber_count() -> dict[str, Any]:
    """Tenants on paid/premium with a real stripe_subscription_id."""
    pool = get_pool()
    try:
        with pool.connection() as conn:
            row = conn.execute(
                """
                SELECT count(*)::int AS paying_subscribers
                FROM tenants t
                JOIN customers c ON c.tenant_id = t.id
                WHERE lower(t.tier) IN ('premium', 'paid')
                  AND c.stripe_subscription_id IS NOT NULL
                  AND c.stripe_subscription_id <> ''
                """
            ).fetchone()
        return {"ok": True, "paying_subscribers": int(row[0] if row else 0)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "paying_subscribers": 0}


def get_mrr_snapshot() -> dict[str, Any]:
    """Single source of truth for corp finance MRR figures."""
    price = _fetch_standard_price()
    subs = _paying_subscriber_count()
    out: dict[str, Any] = {
        "source": "shared:aegis_corp_orchestrator.finance.mrr.get_mrr_snapshot",
        "price": price,
        "paying_subscribers": subs.get("paying_subscribers", 0),
        "paying_query_ok": bool(subs.get("ok")),
    }
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
                f"{n} paying subscribers × "
                f"${monthly_cents/100:.2f} {currency}/mo "
                f"(from Stripe price {price.get('price_id')})"
            ),
        }
    )
    return out
