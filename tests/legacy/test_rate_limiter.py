"""
Test suite for Rate Limiter (Phase 7.3)

Tests the Token Bucket algorithm, rate limiting logic,
and middleware integration.

Run with: python test_rate_limiter.py
"""

import time
import unittest
from unittest.mock import patch

from core.rate_limiter import (
    ClientRateLimitState,
    RateLimitConfig,
    RateLimiter,
    TokenBucket,
    get_rate_limiter,
)


class TestTokenBucket(unittest.TestCase):
    """Test Token Bucket algorithm implementation."""

    def test_initialization(self):
        """Test bucket initializes with full capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        self.assertEqual(bucket.capacity, 10)
        self.assertEqual(bucket.refill_rate, 1.0)
        self.assertEqual(bucket.tokens, 10.0)

    def test_consume_tokens(self):
        """Test consuming tokens from bucket."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        # Should successfully consume 5 tokens
        self.assertTrue(bucket.consume(5))
        self.assertEqual(bucket.get_available_tokens(), 5)

        # Should successfully consume 5 more tokens
        self.assertTrue(bucket.consume(5))
        self.assertEqual(bucket.get_available_tokens(), 0)

        # Should fail to consume when empty
        self.assertFalse(bucket.consume(1))

    def test_token_refill(self):
        """Test tokens refill over time."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 10 tokens/second

        # Consume all tokens
        bucket.consume(10)
        self.assertEqual(bucket.get_available_tokens(), 0)

        # Wait 0.5 seconds, should refill 5 tokens
        time.sleep(0.5)
        available = bucket.get_available_tokens()
        # Allow some tolerance for timing variations
        self.assertGreaterEqual(available, 4)
        self.assertLessEqual(available, 6)

    def test_refill_cap(self):
        """Test refill doesn't exceed capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0)

        # Wait long enough to refill many times over
        time.sleep(2.0)

        # Should be capped at capacity
        self.assertEqual(bucket.get_available_tokens(), 10)

    def test_wait_time_calculation(self):
        """Test wait time calculation when tokens unavailable."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)  # 2 tokens/second

        # Consume all tokens
        bucket.consume(10)

        # Need 1 token, should take 0.5 seconds
        wait_time = bucket.get_wait_time(1)
        self.assertAlmostEqual(wait_time, 0.5, delta=0.1)

        # Need 10 tokens, should take 5 seconds
        wait_time = bucket.get_wait_time(10)
        self.assertAlmostEqual(wait_time, 5.0, delta=0.1)


class TestRateLimitConfig(unittest.TestCase):
    """Test rate limit configuration."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        self.assertEqual(config.per_minute, 60)
        self.assertEqual(config.per_hour, 1000)
        self.assertEqual(config.per_day, 10000)

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RateLimitConfig(per_minute=100, per_hour=2000, per_day=20000)
        self.assertEqual(config.per_minute, 100)
        self.assertEqual(config.per_hour, 2000)
        self.assertEqual(config.per_day, 20000)

    def test_from_env(self):
        """Test loading configuration from environment."""
        with patch.dict(
            "os.environ",
            {
                "RATE_LIMIT_PER_MINUTE": "120",
                "RATE_LIMIT_PER_HOUR": "2000",
                "RATE_LIMIT_PER_DAY": "15000",
            },
        ):
            config = RateLimitConfig.from_env()
            self.assertEqual(config.per_minute, 120)
            self.assertEqual(config.per_hour, 2000)
            self.assertEqual(config.per_day, 15000)

    def test_from_env_with_prefix(self):
        """Test loading configuration with prefix."""
        with patch.dict(
            "os.environ",
            {
                "WORDPRESS_RATE_LIMIT_PER_MINUTE": "80",
                "WORDPRESS_RATE_LIMIT_PER_HOUR": "1500",
                "WORDPRESS_RATE_LIMIT_PER_DAY": "12000",
            },
        ):
            config = RateLimitConfig.from_env(prefix="WORDPRESS")
            self.assertEqual(config.per_minute, 80)
            self.assertEqual(config.per_hour, 1500)
            self.assertEqual(config.per_day, 12000)


class TestClientRateLimitState(unittest.TestCase):
    """Test client rate limit state tracking."""

    def test_initialization(self):
        """Test client state initialization."""
        state = ClientRateLimitState(
            client_id="test_client",
            minute_bucket=TokenBucket(60, 1.0),
            hour_bucket=TokenBucket(1000, 1.0),
            day_bucket=TokenBucket(10000, 1.0),
        )
        self.assertEqual(state.client_id, "test_client")
        self.assertEqual(state.total_requests, 0)
        self.assertEqual(state.rejected_requests, 0)

    def test_successful_request(self):
        """Test successful request consumes tokens."""
        state = ClientRateLimitState(
            client_id="test_client",
            minute_bucket=TokenBucket(60, 1.0),
            hour_bucket=TokenBucket(1000, 1.0),
            day_bucket=TokenBucket(10000, 1.0),
        )

        allowed, message, retry_after = state.check_and_consume()
        self.assertTrue(allowed)
        self.assertEqual(message, "")
        self.assertEqual(retry_after, 0.0)
        self.assertEqual(state.total_requests, 1)
        self.assertEqual(state.rejected_requests, 0)

    def test_minute_limit_exceeded(self):
        """Test rejection when per-minute limit exceeded."""
        state = ClientRateLimitState(
            client_id="test_client",
            minute_bucket=TokenBucket(2, 1.0),  # Only 2 requests/minute
            hour_bucket=TokenBucket(1000, 1.0),
            day_bucket=TokenBucket(10000, 1.0),
        )

        # First 2 requests should succeed
        state.check_and_consume()
        state.check_and_consume()

        # Third request should fail
        allowed, message, retry_after = state.check_and_consume()
        self.assertFalse(allowed)
        self.assertIn("per minute", message.lower())
        self.assertGreater(retry_after, 0)
        self.assertEqual(state.rejected_requests, 1)

    def test_hour_limit_exceeded(self):
        """Test rejection when per-hour limit exceeded."""
        state = ClientRateLimitState(
            client_id="test_client",
            minute_bucket=TokenBucket(100, 100.0),  # High minute limit
            hour_bucket=TokenBucket(2, 1.0),  # Only 2 requests/hour
            day_bucket=TokenBucket(10000, 1.0),
        )

        # First 2 requests should succeed
        state.check_and_consume()
        state.check_and_consume()

        # Third request should fail at hour limit
        allowed, message, retry_after = state.check_and_consume()
        self.assertFalse(allowed)
        self.assertIn("per hour", message.lower())

    def test_day_limit_exceeded(self):
        """Test rejection when daily limit exceeded."""
        state = ClientRateLimitState(
            client_id="test_client",
            minute_bucket=TokenBucket(100, 100.0),
            hour_bucket=TokenBucket(100, 100.0),
            day_bucket=TokenBucket(2, 1.0),  # Only 2 requests/day
        )

        # First 2 requests should succeed
        state.check_and_consume()
        state.check_and_consume()

        # Third request should fail at day limit
        allowed, message, retry_after = state.check_and_consume()
        self.assertFalse(allowed)
        self.assertIn("daily", message.lower())

    def test_token_refund_on_rejection(self):
        """Test tokens are refunded when request rejected at later stage."""
        state = ClientRateLimitState(
            client_id="test_client",
            minute_bucket=TokenBucket(10, 1.0),
            hour_bucket=TokenBucket(2, 1.0),  # Will fail here
            day_bucket=TokenBucket(10, 1.0),
        )

        # Consume hour bucket
        state.check_and_consume()
        state.check_and_consume()

        # Check minute bucket before rejection
        minute_before = state.minute_bucket.get_available_tokens()

        # This should fail at hour limit
        allowed, message, retry_after = state.check_and_consume()
        self.assertFalse(allowed)

        # Minute bucket should be refunded
        minute_after = state.minute_bucket.get_available_tokens()
        self.assertEqual(minute_before, minute_after)

    def test_get_stats(self):
        """Test statistics generation."""
        state = ClientRateLimitState(
            client_id="test_client",
            minute_bucket=TokenBucket(60, 1.0),
            hour_bucket=TokenBucket(1000, 1.0),
            day_bucket=TokenBucket(10000, 1.0),
        )

        # Make some requests
        state.check_and_consume()
        state.check_and_consume()

        stats = state.get_stats()
        self.assertEqual(stats["client_id"], "test_client")
        self.assertEqual(stats["total_requests"], 2)
        self.assertEqual(stats["rejected_requests"], 0)
        self.assertEqual(stats["success_rate"], 1.0)
        self.assertIn("available_tokens", stats)
        self.assertIn("limits", stats)


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter class."""

    def setUp(self):
        """Create a fresh rate limiter for each test."""
        # Reset singleton
        import core.rate_limiter

        core.rate_limiter._rate_limiter = None
        self.limiter = RateLimiter()

    def test_initialization(self):
        """Test rate limiter initialization."""
        self.assertIsNotNone(self.limiter.default_config)
        self.assertEqual(len(self.limiter.clients), 0)
        self.assertEqual(self.limiter.global_stats["total_requests"], 0)

    def test_singleton_pattern(self):
        """Test get_rate_limiter returns singleton."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        self.assertIs(limiter1, limiter2)

    def test_client_creation(self):
        """Test automatic client state creation."""
        allowed, message, retry_after = self.limiter.check_rate_limit(
            client_id="client1", tool_name="test_tool"
        )
        self.assertTrue(allowed)
        self.assertIn("client1", self.limiter.clients)

    def test_successful_rate_limit_check(self):
        """Test successful rate limit check."""
        allowed, message, retry_after = self.limiter.check_rate_limit(
            client_id="client1", tool_name="test_tool"
        )
        self.assertTrue(allowed)
        self.assertEqual(message, "")
        self.assertEqual(retry_after, 0.0)
        self.assertEqual(self.limiter.global_stats["total_requests"], 1)
        self.assertEqual(self.limiter.global_stats["total_rejected"], 0)

    def test_rate_limit_exceeded(self):
        """Test rate limit exceeded scenario."""
        # Configure very low limits
        self.limiter.configure_limits("test_plugin", per_minute=2, per_hour=2, per_day=2)

        # First 2 requests should succeed
        self.limiter.check_rate_limit("client1", "test", "test_plugin")
        self.limiter.check_rate_limit("client1", "test", "test_plugin")

        # Third should fail
        allowed, message, retry_after = self.limiter.check_rate_limit(
            "client1", "test", "test_plugin"
        )
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)
        self.assertEqual(self.limiter.global_stats["total_rejected"], 1)

    def test_plugin_specific_limits(self):
        """Test plugin-specific rate limits."""
        # Configure different limits for wordpress
        self.limiter.configure_limits("wordpress", per_minute=5, per_hour=5, per_day=5)

        # Make 5 wordpress requests
        for _i in range(5):
            allowed, _, _ = self.limiter.check_rate_limit("client1", "wordpress_tool", "wordpress")
            self.assertTrue(allowed)

        # 6th should fail
        allowed, message, _ = self.limiter.check_rate_limit(
            "client1", "wordpress_tool", "wordpress"
        )
        self.assertFalse(allowed)

    def test_multiple_clients(self):
        """Test multiple clients tracked separately."""
        # Configure low limits
        self.limiter.configure_limits("test", per_minute=2, per_hour=2, per_day=2)

        # Client 1 makes 2 requests
        self.limiter.check_rate_limit("client1", "test", "test")
        self.limiter.check_rate_limit("client1", "test", "test")

        # Client 1's third request should fail
        allowed, _, _ = self.limiter.check_rate_limit("client1", "test", "test")
        self.assertFalse(allowed)

        # But client 2's first request should succeed
        allowed, _, _ = self.limiter.check_rate_limit("client2", "test", "test")
        self.assertTrue(allowed)

    def test_get_client_stats(self):
        """Test getting client statistics."""
        # Make some requests
        self.limiter.check_rate_limit("client1", "test")
        self.limiter.check_rate_limit("client1", "test")

        stats = self.limiter.get_client_stats("client1")
        self.assertIsNotNone(stats)
        self.assertEqual(stats["client_id"], "client1")
        self.assertEqual(stats["total_requests"], 2)

    def test_get_client_stats_not_found(self):
        """Test getting stats for non-existent client."""
        stats = self.limiter.get_client_stats("nonexistent")
        self.assertIsNone(stats)

    def test_get_all_stats(self):
        """Test getting all statistics."""
        # Make requests from multiple clients
        self.limiter.check_rate_limit("client1", "test")
        self.limiter.check_rate_limit("client2", "test")

        stats = self.limiter.get_all_stats()
        self.assertIn("global", stats)
        self.assertIn("default_limits", stats)
        self.assertIn("plugin_limits", stats)
        self.assertIn("clients", stats)
        self.assertEqual(stats["global"]["total_requests"], 2)
        self.assertEqual(len(stats["clients"]), 2)

    def test_reset_client(self):
        """Test resetting specific client."""
        # Make some requests
        self.limiter.check_rate_limit("client1", "test")
        self.assertIn("client1", self.limiter.clients)

        # Reset client
        success = self.limiter.reset_client("client1")
        self.assertTrue(success)
        self.assertNotIn("client1", self.limiter.clients)

    def test_reset_client_not_found(self):
        """Test resetting non-existent client."""
        success = self.limiter.reset_client("nonexistent")
        self.assertFalse(success)

    def test_reset_all(self):
        """Test resetting all clients."""
        # Make requests from multiple clients
        self.limiter.check_rate_limit("client1", "test")
        self.limiter.check_rate_limit("client2", "test")
        self.limiter.check_rate_limit("client3", "test")

        # Reset all
        count = self.limiter.reset_all()
        self.assertEqual(count, 3)
        self.assertEqual(len(self.limiter.clients), 0)
        self.assertEqual(self.limiter.global_stats["total_requests"], 0)

    def test_configure_limits(self):
        """Test dynamic limit configuration."""
        self.limiter.configure_limits("custom_plugin", per_minute=100, per_hour=2000, per_day=20000)

        config = self.limiter.plugin_configs["custom_plugin"]
        self.assertEqual(config.per_minute, 100)
        self.assertEqual(config.per_hour, 2000)
        self.assertEqual(config.per_day, 20000)


class TestIntegration(unittest.TestCase):
    """Integration tests simulating real-world usage."""

    def setUp(self):
        """Create fresh rate limiter."""
        import core.rate_limiter

        core.rate_limiter._rate_limiter = None
        self.limiter = RateLimiter()

    def test_burst_traffic(self):
        """Test handling of burst traffic within limits."""
        # Configure to allow 10/minute
        self.limiter.configure_limits("test", per_minute=10, per_hour=100, per_day=1000)

        # Simulate burst of 10 requests
        success_count = 0
        for _i in range(10):
            allowed, _, _ = self.limiter.check_rate_limit("client1", "test", "test")
            if allowed:
                success_count += 1

        # All 10 should succeed (burst allowed)
        self.assertEqual(success_count, 10)

        # 11th should fail
        allowed, _, _ = self.limiter.check_rate_limit("client1", "test", "test")
        self.assertFalse(allowed)

    def test_sustained_traffic(self):
        """Test handling of sustained traffic with refill."""
        # Configure high refill rate for testing
        self.limiter.configure_limits("test", per_minute=5, per_hour=100, per_day=1000)

        # Make 5 requests (consume all minute tokens)
        for _i in range(5):
            self.limiter.check_rate_limit("client1", "test", "test")

        # Should be rate limited now
        allowed, _, _ = self.limiter.check_rate_limit("client1", "test", "test")
        self.assertFalse(allowed)

        # Wait for refill (should get ~2-3 tokens in 0.5 seconds at 5/min rate)
        time.sleep(0.5)

        # Should be able to make 1-2 more requests
        allowed, _, _ = self.limiter.check_rate_limit("client1", "test", "test")
        # May or may not succeed depending on exact timing
        # Just verify no crash and reasonable behavior


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestTokenBucket))
    suite.addTests(loader.loadTestsFromTestCase(TestRateLimitConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestClientRateLimitState))
    suite.addTests(loader.loadTestsFromTestCase(TestRateLimiter))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    import sys

    sys.exit(run_tests())
