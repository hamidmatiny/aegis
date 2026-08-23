"""Per-tenant free-tier rate limiting via Redis (fixed window)."""

from __future__ import annotations

from uuid import UUID

import redis

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        from aegis_smb_copilot.config import settings as live_settings

        _redis = redis.Redis.from_url(live_settings.redis_url, decode_responses=True)
    return _redis


def reset_redis_for_tests() -> None:
    global _redis
    _redis = None


class RateLimitExceeded(Exception):
    """Raised when the tenant has exceeded the configured Q&A budget."""

    def __init__(self, tenant_id: UUID, limit: int, window_sec: int) -> None:
        self.tenant_id = tenant_id
        self.limit = limit
        self.window_sec = window_sec
        super().__init__(
            f"rate limit exceeded for tenant {tenant_id}: "
            f"{limit} requests per {window_sec}s"
        )


def enforce_qa_rate_limit(tenant_id: UUID) -> None:
    """Increment the fixed-window counter; raise RateLimitExceeded if over budget."""
    from aegis_smb_copilot.config import settings as live_settings

    limit = live_settings.qa_rate_limit
    window = live_settings.qa_rate_window_sec
    if limit < 1:
        return

    key = f"smb:qa:rl:{tenant_id}"
    client = get_redis()
    count = client.incr(key)
    if count == 1:
        client.expire(key, window)
    if int(count) > limit:
        raise RateLimitExceeded(tenant_id, limit=limit, window_sec=window)
