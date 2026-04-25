"""Rate limiters: slowapi por IP + IdRateLimiter in-memory por chave (external_id, phone, etc)."""
from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque

from slowapi import Limiter
from slowapi.util import get_remote_address

# IP-based (slowapi) — usado nos decoradores @limiter.limit
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)


_RATE_RE = re.compile(r"^\s*(\d+)\s*/\s*(second|minute|hour)s?\s*$", re.I)


def _parse_rate(spec: str) -> tuple[int, float]:
    m = _RATE_RE.match(spec)
    if not m:
        raise ValueError(f"rate spec invalido: {spec!r} (use '5/minute')")
    qty = int(m.group(1))
    unit = m.group(2).lower()
    seconds = {"second": 1.0, "minute": 60.0, "hour": 3600.0}[unit]
    return qty, seconds


class IdRateLimiter:
    """Sliding-window in-memory rate limiter por chave arbitraria.

    Uso:
        otp_id = IdRateLimiter("3/minute")
        if not otp_id.check(external_id):
            raise HTTPException(429, "muitas tentativas")

    Limitacoes: per-process, per-restart. Para multi-worker/HA, trocar por Redis.
    """

    def __init__(self, spec: str) -> None:
        self.max, self.window = _parse_rate(spec)
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max:
                return False
            bucket.append(now)
            return True

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)
