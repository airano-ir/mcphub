"""
Rate Limiting & Throttling for MCP Server (Phase 7.3)

This module implements Token Bucket-based rate limiting to prevent API abuse
and ensure fair resource usage across all MCP clients.

Features:
- Multi-level rate limits (per minute, hour, day)
- Per-client tracking with token bucket algorithm
- Configurable limits per plugin type
- Statistics and monitoring capabilities
- Integration with audit logging

Author: Phase 7.3 Implementation
Date: 2025-01-11
"""

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limits at different time intervals."""

    per_minute: int = 60
    per_hour: int = 1000
    per_day: int = 10000

    @classmethod
    def from_env(cls, prefix: str = "") -> "RateLimitConfig":
        """Create config from environment variables."""
        env_prefix = f"{prefix}_" if prefix else ""
        return cls(
            per_minute=int(os.getenv(f"{env_prefix}RATE_LIMIT_PER_MINUTE", "60")),
            per_hour=int(os.getenv(f"{env_prefix}RATE_LIMIT_PER_HOUR", "1000")),
            per_day=int(os.getenv(f"{env_prefix}RATE_LIMIT_PER_DAY", "10000")),
        )


@dataclass
class TokenBucket:
    """
    Token Bucket implementation for rate limiting.

    The token bucket algorithm allows for burst traffic while maintaining
    an average rate limit over time.
    """

    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = field(default=0.0)
    last_refill: float = field(default_factory=time.time)

    def __post_init__(self):
        """Initialize bucket with full capacity."""
        if self.tokens == 0.0:
            self.tokens = float(self.capacity)

    def refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were available and consumed, False otherwise
        """
        self.refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_available_tokens(self) -> int:
        """Get current number of available tokens."""
        self.refill()
        return int(self.tokens)

    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Calculate wait time in seconds until enough tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Wait time in seconds (0 if tokens already available)
        """
        self.refill()

        if self.tokens >= tokens:
            return 0.0

        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


@dataclass
class ClientRateLimitState:
    """Track rate limit state for a single client."""

    client_id: str
    minute_bucket: TokenBucket
    hour_bucket: TokenBucket
    day_bucket: TokenBucket
    total_requests: int = 0
    rejected_requests: int = 0
    last_request_time: float = field(default_factory=time.time)
    first_request_time: float = field(default_factory=time.time)

    def check_and_consume(self) -> tuple[bool, str, float]:
        """
        Check if request is allowed and consume tokens.

        Returns:
            Tuple of (allowed, reason, retry_after_seconds)
        """
        # Check each time window (most restrictive first)
        if not self.minute_bucket.consume():
            wait_time = self.minute_bucket.get_wait_time()
            self.rejected_requests += 1
            return False, "Rate limit exceeded: too many requests per minute", wait_time

        if not self.hour_bucket.consume():
            wait_time = self.hour_bucket.get_wait_time()
            # Refund the minute token since we're rejecting
            self.minute_bucket.tokens = min(
                self.minute_bucket.capacity, self.minute_bucket.tokens + 1
            )
            self.rejected_requests += 1
            return False, "Rate limit exceeded: too many requests per hour", wait_time

        if not self.day_bucket.consume():
            wait_time = self.day_bucket.get_wait_time()
            # Refund tokens since we're rejecting
            self.minute_bucket.tokens = min(
                self.minute_bucket.capacity, self.minute_bucket.tokens + 1
            )
            self.hour_bucket.tokens = min(self.hour_bucket.capacity, self.hour_bucket.tokens + 1)
            self.rejected_requests += 1
            return False, "Rate limit exceeded: daily limit reached", wait_time

        # All checks passed
        self.total_requests += 1
        self.last_request_time = time.time()
        return True, "", 0.0

    def get_stats(self) -> dict[str, Any]:
        """Get statistics for this client."""
        now = time.time()
        uptime = now - self.first_request_time

        return {
            "client_id": self.client_id,
            "total_requests": self.total_requests,
            "rejected_requests": self.rejected_requests,
            "success_rate": (
                (self.total_requests - self.rejected_requests) / self.total_requests
                if self.total_requests > 0
                else 1.0
            ),
            "available_tokens": {
                "per_minute": self.minute_bucket.get_available_tokens(),
                "per_hour": self.hour_bucket.get_available_tokens(),
                "per_day": self.day_bucket.get_available_tokens(),
            },
            "limits": {
                "per_minute": self.minute_bucket.capacity,
                "per_hour": self.hour_bucket.capacity,
                "per_day": self.day_bucket.capacity,
            },
            "last_request": datetime.fromtimestamp(self.last_request_time, tz=UTC).isoformat(),
            "uptime_seconds": uptime,
        }


class RateLimiter:
    """
    Rate limiter using Token Bucket algorithm.

    Provides multi-level rate limiting (per minute, hour, day) with
    per-client tracking and configurable limits.
    """

    def __init__(self):
        """Initialize rate limiter with default configuration."""
        self.clients: dict[str, ClientRateLimitState] = {}
        self.global_stats = {"total_requests": 0, "total_rejected": 0, "start_time": time.time()}

        # Load default configuration from environment
        self.default_config = RateLimitConfig.from_env()

        # Plugin-specific configurations
        self.plugin_configs: dict[str, RateLimitConfig] = {
            "wordpress": RateLimitConfig.from_env("WORDPRESS"),
            "woocommerce": RateLimitConfig.from_env("WOOCOMMERCE"),
        }

        logger.info(
            "Rate limiter initialized with default limits: "
            f"{self.default_config.per_minute}/min, "
            f"{self.default_config.per_hour}/hour, "
            f"{self.default_config.per_day}/day"
        )

    def _get_or_create_client_state(
        self, client_id: str, plugin_type: str | None = None
    ) -> ClientRateLimitState:
        """Get or create rate limit state for a client."""
        if client_id not in self.clients:
            # Determine which config to use
            config = self.plugin_configs.get(plugin_type, self.default_config)

            # Create token buckets for each time window
            minute_bucket = TokenBucket(
                capacity=config.per_minute,
                refill_rate=config.per_minute / 60.0,  # tokens per second
            )
            hour_bucket = TokenBucket(
                capacity=config.per_hour, refill_rate=config.per_hour / 3600.0
            )
            day_bucket = TokenBucket(capacity=config.per_day, refill_rate=config.per_day / 86400.0)

            self.clients[client_id] = ClientRateLimitState(
                client_id=client_id,
                minute_bucket=minute_bucket,
                hour_bucket=hour_bucket,
                day_bucket=day_bucket,
            )

            logger.debug(f"Created rate limit state for client: {client_id}")

        return self.clients[client_id]

    def check_rate_limit(
        self, client_id: str, tool_name: str | None = None, plugin_type: str | None = None
    ) -> tuple[bool, str, float]:
        """
        Check if request should be allowed based on rate limits.

        Args:
            client_id: Identifier for the client (e.g., auth token hash)
            tool_name: Name of the tool being called (for logging)
            plugin_type: Type of plugin (wordpress, woocommerce, etc.)

        Returns:
            Tuple of (allowed, message, retry_after_seconds)
        """
        # Get or create client state
        client_state = self._get_or_create_client_state(client_id, plugin_type)

        # Update global stats
        self.global_stats["total_requests"] += 1

        # Check and consume tokens
        allowed, message, retry_after = client_state.check_and_consume()

        if not allowed:
            # Track rejection
            client_state.rejected_requests += 1
            self.global_stats["total_rejected"] += 1

            logger.warning(
                f"Rate limit exceeded for client {client_id[:8]}... "
                f"(tool: {tool_name}, reason: {message}, "
                f"retry_after: {retry_after:.1f}s)"
            )
        else:
            logger.debug(
                f"Rate limit check passed for client {client_id[:8]}... " f"(tool: {tool_name})"
            )

        return allowed, message, retry_after

    def get_client_stats(self, client_id: str) -> dict[str, Any] | None:
        """
        Get statistics for a specific client.

        Args:
            client_id: Client identifier

        Returns:
            Client statistics or None if client not found
        """
        if client_id not in self.clients:
            return None

        return self.clients[client_id].get_stats()

    def get_all_stats(self) -> dict[str, Any]:
        """Get global rate limiter statistics."""
        now = time.time()
        uptime = now - self.global_stats["start_time"]

        # Calculate per-client stats
        client_stats = []
        for _client_id, client_state in self.clients.items():
            client_stats.append(client_state.get_stats())

        return {
            "global": {
                "total_requests": self.global_stats["total_requests"],
                "total_rejected": self.global_stats["total_rejected"],
                "rejection_rate": (
                    self.global_stats["total_rejected"] / self.global_stats["total_requests"]
                    if self.global_stats["total_requests"] > 0
                    else 0.0
                ),
                "active_clients": len(self.clients),
                "uptime_seconds": uptime,
                "start_time": datetime.fromtimestamp(
                    self.global_stats["start_time"], tz=UTC
                ).isoformat(),
            },
            "default_limits": {
                "per_minute": self.default_config.per_minute,
                "per_hour": self.default_config.per_hour,
                "per_day": self.default_config.per_day,
            },
            "plugin_limits": {
                plugin: {
                    "per_minute": config.per_minute,
                    "per_hour": config.per_hour,
                    "per_day": config.per_day,
                }
                for plugin, config in self.plugin_configs.items()
            },
            "clients": client_stats,
        }

    def reset_client(self, client_id: str) -> bool:
        """
        Reset rate limit state for a specific client.

        Args:
            client_id: Client identifier

        Returns:
            True if client was reset, False if client not found
        """
        if client_id in self.clients:
            del self.clients[client_id]
            logger.info(f"Reset rate limit state for client: {client_id}")
            return True
        return False

    def reset_all(self) -> int:
        """
        Reset all client rate limit states.

        Returns:
            Number of clients reset
        """
        count = len(self.clients)
        self.clients.clear()
        self.global_stats = {"total_requests": 0, "total_rejected": 0, "start_time": time.time()}
        logger.info(f"Reset rate limit state for {count} clients")
        return count

    def configure_limits(
        self,
        plugin_type: str,
        per_minute: int | None = None,
        per_hour: int | None = None,
        per_day: int | None = None,
    ) -> None:
        """
        Configure rate limits for a specific plugin type.

        Args:
            plugin_type: Plugin type identifier
            per_minute: Requests per minute limit
            per_hour: Requests per hour limit
            per_day: Requests per day limit
        """
        if plugin_type not in self.plugin_configs:
            self.plugin_configs[plugin_type] = RateLimitConfig()

        config = self.plugin_configs[plugin_type]
        if per_minute is not None:
            config.per_minute = per_minute
        if per_hour is not None:
            config.per_hour = per_hour
        if per_day is not None:
            config.per_day = per_day

        logger.info(
            f"Updated rate limits for {plugin_type}: "
            f"{config.per_minute}/min, {config.per_hour}/hour, {config.per_day}/day"
        )


# Singleton instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
