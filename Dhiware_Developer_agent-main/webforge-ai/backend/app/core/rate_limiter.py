"""In-memory sliding-window rate limiter.

Not distributed — this is a single-process, single-user local tool, so a
plain in-memory window per key is sufficient (see the audit note on chat
abuse limits: no Redis/external store needed here).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Return True and record the request if `key` is under its limit
        for the current window, otherwise return False without recording."""
        now = time.monotonic()
        window = self._windows[key]
        while window and now - window[0] > self.window_seconds:
            window.popleft()
        if len(window) >= self.max_requests:
            return False
        window.append(now)
        return True
