import asyncio
import copy
import time
from collections import OrderedDict
from typing import Any, Hashable

from app.core.config import settings


class TTLCache:
    def __init__(self, ttl_seconds: int, max_size: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._items: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: Hashable) -> Any | None:
        if self.ttl_seconds <= 0 or self.max_size <= 0:
            return None

        async with self._lock:
            item = self._items.get(key)
            if item is None:
                return None

            expires_at, value = item
            if expires_at <= time.monotonic():
                self._items.pop(key, None)
                return None

            self._items.move_to_end(key)
            return copy.deepcopy(value)

    async def set(self, key: Hashable, value: Any) -> None:
        if self.ttl_seconds <= 0 or self.max_size <= 0:
            return

        async with self._lock:
            self._items[key] = (time.monotonic() + self.ttl_seconds, copy.deepcopy(value))
            self._items.move_to_end(key)

            while len(self._items) > self.max_size:
                self._items.popitem(last=False)

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()


movie_cache = TTLCache(
    ttl_seconds=settings.MOVIE_CACHE_TTL_SECONDS,
    max_size=settings.MOVIE_CACHE_MAX_SIZE,
)


async def invalidate_movie_cache() -> None:
    await movie_cache.clear()
