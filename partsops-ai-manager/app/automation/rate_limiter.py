"""
Simple in-memory sliding-window rate limiter.
For production, replace with slowapi or similar backed by Redis.
"""
import time
import threading
from collections import defaultdict, deque
from typing import Dict, Tuple

class RateLimiter:
    def __init__(self):
        self._windows: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
    
    def allow(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        now = time.time()
        with self._lock:
            window = self._windows[key]
            # Remove old entries
            while window and window[0] < now - window_seconds:
                window.popleft()
            if len(window) >= limit:
                return False, int(window[0] + window_seconds - now)
            window.append(now)
            return True, 0

# Global singleton
rate_limiter = RateLimiter()
