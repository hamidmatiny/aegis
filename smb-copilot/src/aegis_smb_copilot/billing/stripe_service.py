"""Stripe Checkout, Billing Portal, and webhook handling."""

from __future__ import annotations

import logging
from uuid import UUID

import stripe
from fastapi import HTTPException, status

from aegis_smb_copilot import config
from aegis_smb_copilot.admin.service import set_tenant_tier
from aegis_smb_copilot.db.connection import get_pool

logger = logging.getLogger(__name__)


class StripeNotConfiguredError(RuntimeError):
    """Stripe env vars are missing."""


def _require_stripe() -> None:
    settings = config.settings
    if not settings.stripe_secret_key or not settings.stripe_price_id_standard:
        raise StripeNotConfiguredError("Stripe is not configured")


def _stripe_client() -> None:
    stripe.api_key = config.settings.stripe_secret_key


def _customer_row(tenant_id: UUID) -> tuple[str, str | None, str | None, str]:
    """Return email, stripe_customer_id, stripe_subscription_id, tenant tier."""
    pool = get_pool()
    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT c.email, c.stripe_customer_id, c.stripe_subscription_id, t.tier
            FROM customers c
            JOIN tenants t ON t.id = c.tenant_id
            WHERE c.tenant_id = %s
            """,
            (tenant_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "customer_account_required",
                "message": "Stripe billing requires an email/password customer account",
            },
        )
    return str(row[0]), row[1], row[2], str(row[3])


def create_checkout_session(tenant_id: UUID) -> str:
    """Create a Stripe Checkout subscription session; return redirect URL."""
    _require_stripe()
    _stripe_client()
    email, stripe_customer_id, _sub_id, _tier = _customer_row(tenant_id)
    base = config.settings.portal_base_url.rstrip("/")

    params: dict[str, object] = {
        "mode": "subscription",
        "line_items": [{"price": config.settings.stripe_price_id_standard, "quantity": 1}],
        "success_url": f"{base}/billing?checkout=success",
        "cancel_url": f"{base}/billing?checkout=cancel",
        "metadata": {"tenant_id": str(tenant_id)},
        "client_reference_id": str(tenant_id),
    }
    if stripe_customer_id:
        params["customer"] = stripe_customer_id
    else:
        params["customer_email"] = email

    session = stripe.checkout.Session.create(**params)
    if not session.url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": "stripe_error", "message": "Checkout session missing URL"},
        )
    return session.url


def create_billing_portal_session(tenant_id: UUID) -> str:
    """Create a Stripe Billing Portal session for self-serve manage/cancel."""
    _require_stripe()
    _stripe_client()
    _email, stripe_customer_id, _sub_id, _tier = _customer_row(tenant_id)
    if not stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "no_stripe_customer",
                "message": "Complete checkout before opening the billing portal",
            },
        )
    base = config.settings.portal_base_url.rstrip("/")
    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=f"{base}/billing",
    )
    return session.url


def _persist_stripe_ids(
    tenant_id: UUID,
    *,
    stripe_customer_id: str | None,
    stripe_subscription_id: str | None,
) -> None:
    pool = get_pool()
    with pool.connection() as conn:
        conn.execute(
            """
            UPDATE customers
            SET stripe_customer_id = COALESCE(%s, stripe_customer_id),
                stripe_subscription_id = COALESCE(%s, stripe_subscription_id)
            WHERE tenant_id = %s
            """,
            (stripe_customer_id, stripe_subscription_id, tenant_id),
        )


def handle_checkout_session_completed(session: dict[str, object]) -> None:
    """Upgrade tenant tier idempotently after successful Checkout."""
    metadata = session.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("checkout session missing metadata")
    tenant_raw = metadata.get("tenant_id")
    if not tenant_raw:
        raise ValueError("checkout session metadata missing tenant_id")
    tenant_id = UUID(str(tenant_raw))

    stripe_customer_id = session.get("customer")
    stripe_subscription_id = session.get("subscription")
    customer_id_str = str(stripe_customer_id) if stripe_customer_id else None
    subscription_id_str = str(stripe_subscription_id) if stripe_subscription_id else None

    _email, existing_customer, existing_sub, tier = _customer_row(tenant_id)

    if (
        subscription_id_str
        and existing_sub
        and existing_sub == subscription_id_str
    ):
        logger.info(
            "checkout.session.completed already processed for tenant %s subscription %s",
            tenant_id,
            subscription_id_str,
        )
        return

    _persist_stripe_ids(
        tenant_id,
        stripe_customer_id=customer_id_str,
        stripe_subscription_id=subscription_id_str,
    )
    if tier != "premium":
        set_tenant_tier(tenant_id, "paid")
    logger.info("tenant %s upgraded to paid via Stripe checkout", tenant_id)


def construct_webhook_event(payload: bytes, signature: str | None) -> stripe.Event:
    """Verify Stripe signature and parse webhook event."""
    if not config.settings.stripe_webhook_secret:
        raise StripeNotConfiguredError("Stripe webhook secret is not configured")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"type": "missing_signature", "message": "Stripe-Signature header required"},
        )
    try:
        return stripe.Webhook.construct_event(
            payload,
            signature,
            config.settings.stripe_webhook_secret,
        )
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"type": "invalid_signature", "message": "Stripe signature verification failed"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"type": "invalid_payload", "message": "Invalid webhook payload"},
        ) from exc
