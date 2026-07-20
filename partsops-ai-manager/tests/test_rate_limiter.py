"""Tests for intake rate limiter."""
import pytest
from app.automation.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    return RateLimiter()


def test_allows_within_limit(limiter):
    for _ in range(10):
        allowed, _ = limiter.allow("intake:tenant-a:127.0.0.1", limit=10, window_seconds=60)
        assert allowed is True


def test_blocks_over_limit(limiter):
    key = "intake:tenant-a:127.0.0.1"
    for _ in range(10):
        limiter.allow(key, limit=10, window_seconds=60)
    allowed, retry_after = limiter.allow(key, limit=10, window_seconds=60)
    assert allowed is False
    assert retry_after > 0


def test_independent_tenants(limiter):
    key_a = "intake:tenant-a:127.0.0.1"
    key_b = "intake:tenant-b:127.0.0.1"
    for _ in range(10):
        limiter.allow(key_a, limit=10, window_seconds=60)
    allowed, _ = limiter.allow(key_b, limit=10, window_seconds=60)
    assert allowed is True
