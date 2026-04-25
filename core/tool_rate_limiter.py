"""Per-tool, per-user rate limiting (F.5a.6).

Provides a small token-bucket limiter keyed by (user_id, tool_name) for
expensive tools such as AI image generation and chunked-upload finish.
Admin / env-fallback callers (``user_id is None``) are exempt.

Intentionally minimal — separate from :mod:`core.rate_limiter` (which is a
global per-client limiter). This one is scoped to specific tools with
small hourly caps.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from core.rate_limiter import TokenBucket

logger = logging.getLogger(__name__)


# Default caps (per hour per user). Documented in ROADMAP F.5a.6.
DEFAULT_LIMITS: dict[str, int] = {
    "wordpress_generate_and_upload_image": 10,
    "wordpress_upload_media_chunked_finish": 30,
}


@dataclass
class ToolRateLimitError(Exception):
    """Raised when a per-tool limit is exceeded."""

    tool_name: str
    limit_per_hour: int
    retry_after_seconds: float

    def __post_init__(self) -> None:
        super().__init__(
            f"Per-tool rate limit exceeded for '{self.tool_name}' "
            f"({self.limit_per_hour}/hour per user). "
            f"Retry in {self.retry_after_seconds:.0f}s."
        )

    def to_dict(self) -> dict:
        return {
            "error_code": "TOOL_RATE_LIMITED",
            "message": str(self),
            "details": {
                "tool": self.tool_name,
                "limit_per_hour": self.limit_per_hour,
                "retry_after_seconds": round(self.retry_after_seconds, 2),
            },
        }


class PerToolRateLimiter:
    """Token-bucket limiter keyed by (user_id, tool_name).

    ``check(tool, user_id)`` consumes one token and raises
    :class:`ToolRateLimitError` when the user is over quota. Admin / env
    callers (``user_id`` is None or empty) are exempt.
    """

    def __init__(self, limits: dict[str, int] | None = None) -> None:
        self._limits = dict(limits if limits is not None else DEFAULT_LIMITS)
        self._buckets: dict[tuple[str, str], TokenBucket] = {}
        self._lock = threading.Lock()

    def configure(self, tool_name: str, per_hour: int) -> None:
        """Override the per-hour cap for a tool."""
        self._limits[tool_name] = per_hour
        # Existing buckets keep their old capacity until reset — tests can
        # reset() to re-read the new limit.

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def check(self, tool_name: str, user_id: str | None) -> None:
        """Consume one token for (user_id, tool_name). Exempt when user_id is falsy."""
        if not user_id:
            return
        limit = self._limits.get(tool_name)
        if limit is None or limit <= 0:
            return

        key = (user_id, tool_name)
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(capacity=limit, refill_rate=limit / 3600.0)
                self._buckets[key] = bucket

        if not bucket.consume(1):
            wait = bucket.get_wait_time(1)
            logger.warning(
                "Per-tool rate limit hit: user=%s tool=%s limit=%d/h retry_after=%.1fs",
                user_id,
                tool_name,
                limit,
                wait,
            )
            raise ToolRateLimitError(
                tool_name=tool_name, limit_per_hour=limit, retry_after_seconds=wait
            )


_limiter: PerToolRateLimiter | None = None


def get_tool_rate_limiter() -> PerToolRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = PerToolRateLimiter()
    return _limiter


def set_tool_rate_limiter(limiter: PerToolRateLimiter | None) -> None:
    """Override the singleton (used by tests)."""
    global _limiter
    _limiter = limiter
