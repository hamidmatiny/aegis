"""Scheduler due-check and allowlist helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from aegis_corp_orchestrator.runner import scheduler as sched


def test_due_matches_current_minute_on_first_fire() -> None:
    sched._last_fire.clear()
    now = datetime(2026, 9, 15, 7, 0, 30, tzinfo=timezone.utc)
    assert sched._due("0 7 * * *", "executive/ceo", now) is True


def test_due_false_outside_cron_minute() -> None:
    sched._last_fire.clear()
    now = datetime(2026, 9, 15, 7, 1, 5, tzinfo=timezone.utc)
    assert sched._due("0 7 * * *", "executive/ceo", now) is False


def test_due_false_when_already_fired_this_minute() -> None:
    now = datetime(2026, 9, 15, 7, 0, 45, tzinfo=timezone.utc)
    sched._last_fire["executive/ceo"] = now.replace(second=0, microsecond=0)
    assert sched._due("0 7 * * *", "executive/ceo", now) is False
    sched._last_fire.clear()


def test_allowlist_none_when_empty(monkeypatch) -> None:
    monkeypatch.setattr(sched.settings, "scheduler_allowlist", "")
    assert sched._allowlist() is None


def test_allowlist_parses_ceo_only(monkeypatch) -> None:
    monkeypatch.setattr(sched.settings, "scheduler_allowlist", "executive/ceo")
    assert sched._allowlist() == {"executive/ceo"}
