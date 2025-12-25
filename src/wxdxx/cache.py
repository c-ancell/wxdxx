"""TTL-based in-memory cache."""

import time
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheEntry(Generic[V]):
    """A cached value with expiration time."""

    value: V
    expires_at: float


class TTLCache(Generic[K, V]):
    """In-memory cache with time-based expiration.

    Entries automatically expire after their TTL. Size-based eviction
    removes oldest entries when capacity is reached.
    """

    def __init__(self, default_ttl: float, max_size: int = 100) -> None:
        """Initialize cache.

        Args:
            default_ttl: Default time-to-live in seconds for cached entries.
            max_size: Maximum number of entries before eviction.
        """
        self._cache: dict[K, CacheEntry[V]] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size

    def get(self, key: K) -> V | None:
        """Get value if exists and not expired.

        Args:
            key: Cache key to look up.

        Returns:
            Cached value if found and not expired, None otherwise.
        """
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._cache[key]
            return None
        return entry.value

    def set(self, key: K, value: V, ttl: float | None = None) -> None:
        """Set value with TTL, evicting oldest if at capacity.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Optional TTL override in seconds. Uses default if not specified.
        """
        # Evict oldest if at capacity (and this is a new key)
        if len(self._cache) >= self._max_size and key not in self._cache:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        expires_at = time.monotonic() + (ttl if ttl is not None else self._default_ttl)
        self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    def invalidate(self, key: K) -> None:
        """Remove specific key from cache.

        Args:
            key: Cache key to remove.
        """
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._cache.clear()

    def cleanup_expired(self) -> None:
        """Remove all expired entries from the cache."""
        now = time.monotonic()
        expired = [k for k, v in self._cache.items() if now > v.expires_at]
        for key in expired:
            del self._cache[key]

    def __contains__(self, key: K) -> bool:
        """Check if key exists and is not expired.

        Args:
            key: Cache key to check.

        Returns:
            True if key exists and is not expired.
        """
        return self.get(key) is not None

    def __len__(self) -> int:
        """Return count of non-expired entries.

        Note: This triggers cleanup of expired entries.
        """
        self.cleanup_expired()
        return len(self._cache)
