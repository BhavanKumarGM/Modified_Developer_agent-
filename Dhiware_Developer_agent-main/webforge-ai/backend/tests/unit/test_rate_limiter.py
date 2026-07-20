"""Unit tests for the sliding-window RateLimiter primitive backing
audit item 4.5's per-project chat rate limit."""
import time

from app.core.rate_limiter import RateLimiter


def test_allows_up_to_max_requests():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("p1") is True
    assert limiter.allow("p1") is True
    assert limiter.allow("p1") is True
    assert limiter.allow("p1") is False


def test_different_keys_have_independent_limits():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("p1") is True
    assert limiter.allow("p2") is True
    assert limiter.allow("p1") is False
    assert limiter.allow("p2") is False


def test_requests_are_allowed_again_after_the_window_passes():
    limiter = RateLimiter(max_requests=1, window_seconds=0.05)
    assert limiter.allow("p1") is True
    assert limiter.allow("p1") is False
    time.sleep(0.06)
    assert limiter.allow("p1") is True
