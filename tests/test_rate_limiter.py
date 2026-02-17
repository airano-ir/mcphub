"""Tests for Rate Limiter (core/rate_limiter.py)."""

import pytest

from core.rate_limiter import ClientRateLimitState, RateLimitConfig, RateLimiter, TokenBucket


class TestRateLimitConfig:
    """Test rate limit configuration."""

    def test_defaults(self):
        config = RateLimitConfig()
        assert config.per_minute == 60
        assert config.per_hour == 1000
        assert config.per_day == 10000

    def test_custom_values(self):
        config = RateLimitConfig(per_minute=10, per_hour=100, per_day=500)
        assert config.per_minute == 10

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "30")
        monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "500")
        monkeypatch.setenv("RATE_LIMIT_PER_DAY", "5000")
        config = RateLimitConfig.from_env()
        assert config.per_minute == 30
        assert config.per_hour == 500
        assert config.per_day == 5000

    def test_from_env_with_prefix(self, monkeypatch):
        monkeypatch.setenv("WP_RATE_LIMIT_PER_MINUTE", "20")
        config = RateLimitConfig.from_env("WP")
        assert config.per_minute == 20


class TestTokenBucket:
    """Test token bucket algorithm."""

    def test_initial_capacity(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.get_available_tokens() == 10

    def test_consume_success(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(1) is True
        assert bucket.get_available_tokens() == 9

    def test_consume_multiple(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(5) is True
        assert bucket.get_available_tokens() == 5

    def test_consume_exceeds_capacity(self):
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.consume(6) is False
        # Tokens should not be consumed on failure
        assert bucket.get_available_tokens() == 5

    def test_consume_until_empty(self):
        bucket = TokenBucket(capacity=3, refill_rate=0.0)  # no refill
        assert bucket.consume(1) is True
        assert bucket.consume(1) is True
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False

    def test_get_wait_time_when_available(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.get_wait_time(1) == 0.0

    def test_get_wait_time_when_empty(self):
        bucket = TokenBucket(capacity=1, refill_rate=1.0)
        bucket.consume(1)
        wait = bucket.get_wait_time(1)
        assert wait > 0


class TestClientRateLimitState:
    """Test per-client rate limit state."""

    def _make_client(self, per_minute=5, per_hour=100, per_day=1000):
        return ClientRateLimitState(
            client_id="test-client",
            minute_bucket=TokenBucket(capacity=per_minute, refill_rate=per_minute / 60.0),
            hour_bucket=TokenBucket(capacity=per_hour, refill_rate=per_hour / 3600.0),
            day_bucket=TokenBucket(capacity=per_day, refill_rate=per_day / 86400.0),
        )

    def test_allowed_request(self):
        client = self._make_client()
        allowed, reason, retry_after = client.check_and_consume()
        assert allowed is True
        assert reason == ""
        assert retry_after == 0.0

    def test_minute_limit_exceeded(self):
        client = self._make_client(per_minute=2)
        client.check_and_consume()
        client.check_and_consume()
        allowed, reason, retry_after = client.check_and_consume()
        assert allowed is False
        assert "per minute" in reason

    def test_stats(self):
        client = self._make_client()
        client.check_and_consume()
        client.check_and_consume()
        stats = client.get_stats()
        assert stats["client_id"] == "test-client"
        assert stats["total_requests"] == 2


class TestRateLimiter:
    """Test the main RateLimiter class."""

    @pytest.fixture
    def limiter(self):
        return RateLimiter()

    def test_first_request_allowed(self, limiter):
        allowed, msg, retry = limiter.check_rate_limit("client1")
        assert allowed is True

    def test_different_clients_independent(self, limiter):
        for _ in range(50):
            limiter.check_rate_limit("client1")
        allowed, _, _ = limiter.check_rate_limit("client2")
        assert allowed is True

    def test_get_client_stats(self, limiter):
        limiter.check_rate_limit("client1")
        stats = limiter.get_client_stats("client1")
        assert stats is not None
        assert stats["client_id"] == "client1"

    def test_get_client_stats_unknown(self, limiter):
        assert limiter.get_client_stats("unknown") is None

    def test_reset_client(self, limiter):
        limiter.check_rate_limit("client1")
        assert limiter.reset_client("client1") is True
        assert limiter.get_client_stats("client1") is None

    def test_reset_nonexistent_client(self, limiter):
        assert limiter.reset_client("nonexistent") is False

    def test_reset_all(self, limiter):
        limiter.check_rate_limit("client1")
        limiter.check_rate_limit("client2")
        count = limiter.reset_all()
        assert count == 2
        assert limiter.get_client_stats("client1") is None

    def test_get_all_stats(self, limiter):
        limiter.check_rate_limit("client1")
        stats = limiter.get_all_stats()
        assert "global" in stats
        assert "default_limits" in stats
        assert stats["global"]["total_requests"] >= 1
        assert stats["global"]["active_clients"] == 1

    def test_configure_limits(self, limiter):
        limiter.configure_limits("n8n", per_minute=10, per_hour=50)
        assert limiter.plugin_configs["n8n"].per_minute == 10
        assert limiter.plugin_configs["n8n"].per_hour == 50
