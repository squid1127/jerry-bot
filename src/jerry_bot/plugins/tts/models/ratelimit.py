"""Simple rate limiter for controlling the rate of TTS requests."""

import asyncio
import time


class RateLimiter:
    """A simple rate limiter that allows a certain number of calls within a specified period."""
    
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._tokens = max_calls
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a token from the rate limiter, waiting if necessary."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last
                self._tokens = min(self.max_calls, self._tokens + elapsed * (self.max_calls / self.period))
                self._last = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await asyncio.sleep((1 - self._tokens) * (self.period / self.max_calls))