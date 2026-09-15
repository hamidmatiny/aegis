"""Tests for test-account classification and live-mode MRR gating."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from aegis_smb_session.test_accounts import classify_test_account


@pytest.mark.parametrize(
    "email,slug,expected",
    [
        ("stripe-e2e-ca2f9ee6@example.com", "stripe-e2e-ca2f9ee6", True),
        ("user@example.com", "random-slug", True),
        ("landing-smoke+1@example.test", "ui-reg-1", True),
        ("e2e-123@elsewhere.com", "real-co", True),
        ("navtest-abc", None, False),  # email none, slug via other arg
        ("real.customer@acme.io", "acme-co", False),
    ],
)
def test_classify_patterns(email: str | None, slug: str | None, expected: bool) -> None:
    if email == "navtest-abc":
        assert classify_test_account(slug="navtest-abc") is True
        return
    assert classify_test_account(email=email, slug=slug) is expected


def test_classify_force_and_internal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_INTERNAL_ACCOUNT_EMAILS", "owner@personal.example")
    assert classify_test_account(email="owner@personal.example", slug="owner") is True
    monkeypatch.setenv("AEGIS_FORCE_TEST_ACCOUNTS", "1")
    assert classify_test_account(email="legit@acme.io", slug="legit") is True


def test_mrr_rejects_test_mode_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from aegis_corp_orchestrator import config as config_mod
    from aegis_corp_orchestrator.finance import mrr as mrr_mod

    monkeypatch.setattr(
        mrr_mod.settings,
        "stripe_secret_key",
        "sk_test_fake",
        raising=False,
    )
    monkeypatch.setattr(
        mrr_mod.settings,
        "stripe_price_id_standard",
        "price_x",
        raising=False,
    )
    # Re-bind settings object fields on the module's settings
    config_mod.settings.stripe_secret_key = "sk_test_fake"
    config_mod.settings.stripe_price_id_standard = "price_x"
    mrr_mod.settings = config_mod.settings

    snap = mrr_mod.get_mrr_snapshot()
    assert snap["unavailable"] is True
    assert snap["reason"] == "stripe_not_live_mode"


def test_mrr_excludes_unverified_db_subscription(monkeypatch: pytest.MonkeyPatch) -> None:
    from aegis_corp_orchestrator import config as config_mod
    from aegis_corp_orchestrator.finance import mrr as mrr_mod

    config_mod.settings.stripe_secret_key = "sk_live_" + ("x" * 90)
    config_mod.settings.stripe_price_id_standard = "price_live"
    mrr_mod.settings = config_mod.settings

    monkeypatch.setattr(
        mrr_mod,
        "_fetch_standard_price",
        lambda: {
            "ok": True,
            "price_id": "price_live",
            "unit_amount": 2900,
            "currency": "CAD",
            "interval": "month",
            "interval_count": 1,
            "livemode": True,
        },
    )
    monkeypatch.setattr(
        mrr_mod,
        "_candidate_paying_rows",
        lambda: {
            "ok": True,
            "candidates": [
                {
                    "tenant_id": "t1",
                    "slug": "stripe-e2e-ca2f9ee6",
                    "email": "stripe-e2e-ca2f9ee6@example.com",
                    "stripe_subscription_id": "sub_test_fake",
                }
            ],
        },
    )
    monkeypatch.setattr(
        mrr_mod,
        "_verify_live_subscription",
        lambda secret, sub_id: {
            "ok": False,
            "reason": "not_found_in_live_stripe",
            "subscription_id": sub_id,
        },
    )

    snap = mrr_mod.get_mrr_snapshot()
    assert snap["unavailable"] is False
    assert snap["paying_subscribers"] == 0
    assert snap["mrr_usd"] == 0.0
    assert snap["mrr_display"] == "$0.00 CAD"
    assert snap["excluded_unverified"] == 1
    assert snap["live_mode_verified"] is True
