"""Hız sınırı (Sprint 94 E3/E9) — yeni bağımlılık yok, süreç içi kayan pencere.

Anahtar kullanıcı kimliğidir: tüm trafik Next / Tailscale üzerinden 127.0.0.1'den geldiği için IP anlamsız,
`X-Forwarded-For` ise istemcinin yazdığı değer (taklit edilebilir). Giriş kapalıysa (yerel / test) bağlantı adresi.
"""

from __future__ import annotations

import collections
import time

from fastapi import HTTPException, Request

_WINDOW = 60.0
_BUCKETS_MAX = 2000
_buckets: "collections.OrderedDict[str, collections.deque]" = collections.OrderedDict()


def client_key(request: Request) -> str:
    """İsteğin sahibi: oturumdaki kullanıcı, yoksa bağlantı adresi."""
    user = getattr(getattr(request, "state", None), "user", None)
    if user is not None:
        return f"u:{user.id}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def check_rate(request: Request, name: str, limit: int, window: float = _WINDOW) -> None:
    """`name` (uç noktası grubu) için bu kullanıcının son `window` saniyedeki istek sayısı `limit`'i aşarsa 429."""
    now = time.monotonic()
    key = f"{name}:{client_key(request)}"
    bucket = _buckets.get(key)
    if bucket is None:
        bucket = collections.deque()
        _buckets[key] = bucket
        while len(_buckets) > _BUCKETS_MAX:
            _buckets.popitem(last=False)
    else:
        _buckets.move_to_end(key)
    while bucket and bucket[0] <= now - window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(429, "Çok fazla istek — lütfen biraz bekleyin")
    bucket.append(now)


def reset() -> None:
    """Testler için."""
    _buckets.clear()
