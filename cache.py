import time
from typing import Any, Optional
from functools import wraps

_store: dict[str, tuple[Any, float]] = {}
DEFAULT_TTL = 3600  # 1 hour


def cache_get(key: str) -> Optional[Any]:
    entry = _store.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.time() > expires_at:
        del _store[key]
        return None
    return value


def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    _store[key] = (value, time.time() + ttl)


def cached(ttl: int = DEFAULT_TTL):
    """Async function cache decorator."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            hit = cache_get(key)
            if hit is not None:
                return hit
            result = await func(*args, **kwargs)
            if result:
                cache_set(key, result, ttl)
            return result
        return wrapper
    return decorator
