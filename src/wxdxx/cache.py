"""TTL-based in-memory cache."""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from .models.alert import WFOAlert
    from .models.md import MesoscaleDiscussion
    from .models.observation import Observation
    from .models.outlook import ConvectiveOutlook
    from .models.watch import Watch
    from .models.wfo import WFOProduct

K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")

# Default TTLs by category (seconds)
DEFAULT_TTLS: dict[str, float] = {
    "outlook": 300.0,  # 5 minutes
    "md": 600.0,  # 10 minutes
    "watch": 600.0,  # 10 minutes
    "alert": 120.0,  # 2 minutes
    "product": 1800.0,  # 30 minutes
    "zone": 86400.0,  # 24 hours
    "list": 300.0,  # 5 minutes
    "ticker": 60.0,  # 1 minute
    "observation": 600.0,  # 10 minutes (METAR updates every 10-20 min)
}

# Reduced TTL for empty content (seconds)
EMPTY_CONTENT_TTL = 30.0

# Content length threshold for "empty" detection
EMPTY_THRESHOLD = 100


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


@dataclass
class CachedEntry(Generic[T]):
    """A cached product with metadata for staleness and content state tracking."""

    value: T
    created_at: float  # time.monotonic() when cached
    expires_at: float  # time.monotonic() when TTL expires
    content_length: int = 0  # Length of text content (for empty detection)
    is_empty: bool = False  # True if content below threshold
    source: str = ""  # spc, nws, wpc, nhc
    category: str = ""  # outlook, md, watch, alert, product, zone, list, ticker
    identifier: str = ""  # day1, 2462, OUN:AFD, etc.


class ProductCache:
    """Unified cache for all weather products with targeted invalidation and state tracking.

    Key format: {source}:{category}:{identifier}

    Sources: spc, nws, wpc (future), nhc (future)
    Categories: outlook, md, watch, alert, product, zone, list, ticker

    Examples:
        - spc:outlook:day1
        - spc:md:2462
        - spc:list:md_active
        - nws:product:ABC123
        - nws:list:OUN:AFD
        - nws:ticker:nationwide
    """

    def __init__(
        self,
        default_ttls: dict[str, float] | None = None,
        empty_content_ttl: float = EMPTY_CONTENT_TTL,
        empty_threshold: int = EMPTY_THRESHOLD,
        max_size: int = 500,
    ) -> None:
        """Initialize the unified product cache.

        Args:
            default_ttls: Override default TTLs by category.
            empty_content_ttl: TTL for products with empty/minimal content.
            empty_threshold: Character count threshold below which content is "empty".
            max_size: Maximum number of entries before LRU eviction.
        """
        self._cache: dict[str, CachedEntry[Any]] = {}
        self._ttls = {**DEFAULT_TTLS, **(default_ttls or {})}
        self._empty_content_ttl = empty_content_ttl
        self._empty_threshold = empty_threshold
        self._max_size = max_size
        # OrderedDict for O(1) LRU operations (vs O(n) list)
        self._access_order: OrderedDict[str, None] = OrderedDict()

    # === Core CRUD Operations ===

    def get(self, key: str) -> Any | None:
        """Get value if exists and not expired.

        Args:
            key: Cache key in format "source:category:identifier"

        Returns:
            Cached value if found and not expired, None otherwise.
        """
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._cache[key]
            self._access_order.pop(key, None)
            return None
        # Update access order for LRU (O(1) with OrderedDict)
        self._access_order.move_to_end(key)
        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
        content_text: str | None = None,
    ) -> None:
        """Set value with optional TTL override and content state tracking.

        Args:
            key: Cache key in format "source:category:identifier"
            value: Value to cache
            ttl: Optional TTL override in seconds
            content_text: Optional text content for empty detection
        """
        # Parse key components
        source, category, identifier = self._parse_key(key)

        # Determine content state
        content_length = len(content_text) if content_text else 0
        is_empty = content_text is not None and content_length < self._empty_threshold

        # Determine TTL
        if ttl is not None:
            effective_ttl = ttl
        elif is_empty:
            effective_ttl = self._empty_content_ttl
        else:
            effective_ttl = self._ttls.get(category, 120.0)

        now = time.monotonic()

        # Evict LRU if at capacity
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._evict_lru()

        entry = CachedEntry(
            value=value,
            created_at=now,
            expires_at=now + effective_ttl,
            content_length=content_length,
            is_empty=is_empty,
            source=source,
            category=category,
            identifier=identifier,
        )

        self._cache[key] = entry

        # Update access order (O(1) with OrderedDict)
        # Only move_to_end if key exists; new keys already go to end
        if key in self._access_order:
            self._access_order.move_to_end(key)
        else:
            self._access_order[key] = None

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache.

        Args:
            key: Cache key to invalidate

        Returns:
            True if key was found and removed, False otherwise
        """
        if key in self._cache:
            del self._cache[key]
            self._access_order.pop(key, None)
            return True
        return False

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._cache.clear()
        self._access_order.clear()

    # === Targeted Invalidation ===

    def invalidate_by_source(self, source: str) -> int:
        """Invalidate all entries from a specific source.

        Args:
            source: Source to invalidate (spc, nws, wpc, nhc)

        Returns:
            Number of entries invalidated
        """
        keys_to_remove = [k for k, e in self._cache.items() if e.source == source]
        for key in keys_to_remove:
            del self._cache[key]
            self._access_order.pop(key, None)
        return len(keys_to_remove)

    def invalidate_by_category(self, category: str) -> int:
        """Invalidate all entries of a specific category.

        Args:
            category: Category to invalidate (outlook, md, watch, etc.)

        Returns:
            Number of entries invalidated
        """
        keys_to_remove = [k for k, e in self._cache.items() if e.category == category]
        for key in keys_to_remove:
            del self._cache[key]
            self._access_order.pop(key, None)
        return len(keys_to_remove)

    def invalidate_by_pattern(
        self,
        source: str | None = None,
        category: str | None = None,
        identifier_prefix: str | None = None,
    ) -> int:
        """Invalidate entries matching a pattern.

        Args:
            source: Optional source filter
            category: Optional category filter
            identifier_prefix: Optional identifier prefix filter

        Returns:
            Number of entries invalidated

        Examples:
            invalidate_by_pattern(source="spc", category="md")  # All SPC MDs
            invalidate_by_pattern(category="list")              # All lists
            invalidate_by_pattern(source="nws", identifier_prefix="OUN")  # OUN products
        """

        def matches(entry: CachedEntry[Any]) -> bool:
            if source is not None and entry.source != source:
                return False
            if category is not None and entry.category != category:
                return False
            if identifier_prefix is not None and not entry.identifier.startswith(
                identifier_prefix
            ):
                return False
            return True

        keys_to_remove = [k for k, e in self._cache.items() if matches(e)]
        for key in keys_to_remove:
            del self._cache[key]
            self._access_order.pop(key, None)
        return len(keys_to_remove)

    # === Content State Tracking ===

    def get_empty_products(self) -> list[str]:
        """Get all cache keys with empty content.

        Returns:
            List of cache keys for products with empty/minimal content
        """
        self._cleanup_expired()
        return [k for k, e in self._cache.items() if e.is_empty]

    def is_empty(self, key: str) -> bool:
        """Check if a cached product has empty content.

        Args:
            key: Cache key to check

        Returns:
            True if entry exists and has empty content, False otherwise
        """
        entry = self._cache.get(key)
        return entry is not None and entry.is_empty

    def mark_populated(self, key: str, content_text: str) -> bool:
        """Mark a previously empty product as now populated.

        Updates the entry's is_empty flag and extends TTL to normal.

        Args:
            key: Cache key to update
            content_text: The new content text

        Returns:
            True if entry was updated, False if not found
        """
        entry = self._cache.get(key)
        if entry is None:
            return False

        content_length = len(content_text)
        is_empty = content_length < self._empty_threshold

        if not is_empty and entry.is_empty:
            # Upgrade from empty to populated - extend TTL
            new_ttl = self._ttls.get(entry.category, 120.0)
            entry.expires_at = time.monotonic() + new_ttl
            entry.is_empty = False
            entry.content_length = content_length

        return True

    # === Staleness Tracking ===

    def get_age(self, key: str) -> float | None:
        """Get age of cached entry in seconds.

        Args:
            key: Cache key

        Returns:
            Seconds since entry was created, or None if not found/expired
        """
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            return None
        return time.monotonic() - entry.created_at

    def get_stale_products(self, max_age: float) -> list[str]:
        """Get cache keys for products older than a threshold.

        Args:
            max_age: Maximum age in seconds

        Returns:
            List of cache keys for products older than max_age
        """
        self._cleanup_expired()
        now = time.monotonic()
        return [k for k, e in self._cache.items() if (now - e.created_at) > max_age]

    def get_time_to_expiry(self, key: str) -> float | None:
        """Get seconds until entry expires.

        Args:
            key: Cache key

        Returns:
            Seconds until expiry, or None if not found/already expired
        """
        entry = self._cache.get(key)
        if entry is None:
            return None
        remaining = entry.expires_at - time.monotonic()
        return remaining if remaining > 0 else None

    # === Metadata Access ===

    def get_entry(self, key: str) -> CachedEntry[Any] | None:
        """Get full cache entry with metadata.

        Args:
            key: Cache key

        Returns:
            CachedEntry with value and metadata, or None if not found/expired
        """
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._cache[key]
            self._access_order.pop(key, None)
            return None
        return entry

    # === Statistics ===

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        self._cleanup_expired()

        by_source: dict[str, int] = {}
        by_category: dict[str, int] = {}
        empty_count = 0

        for entry in self._cache.values():
            by_source[entry.source] = by_source.get(entry.source, 0) + 1
            by_category[entry.category] = by_category.get(entry.category, 0) + 1
            if entry.is_empty:
                empty_count += 1

        return {
            "total_entries": len(self._cache),
            "by_source": by_source,
            "by_category": by_category,
            "empty_count": empty_count,
            "max_size": self._max_size,
        }

    # === Type-Safe Helper Methods ===

    def set_outlook(self, day: str, outlook: ConvectiveOutlook) -> None:
        """Store a convective outlook."""
        self.set(f"spc:outlook:{day}", outlook, content_text=outlook.text)

    def get_outlook(self, day: str) -> ConvectiveOutlook | None:
        """Get a cached convective outlook."""
        return self.get(f"spc:outlook:{day}")

    def set_md(self, number: int, md: MesoscaleDiscussion) -> None:
        """Store a mesoscale discussion."""
        self.set(f"spc:md:{number}", md, content_text=md.text)

    def get_md(self, number: int) -> MesoscaleDiscussion | None:
        """Get a cached mesoscale discussion."""
        return self.get(f"spc:md:{number}")

    def set_watch(self, number: int, watch: Watch) -> None:
        """Store a watch."""
        self.set(f"spc:watch:{number}", watch, content_text=watch.text)

    def get_watch(self, number: int) -> Watch | None:
        """Get a cached watch."""
        return self.get(f"spc:watch:{number}")

    def set_wfo_product(self, product_id: str, product: WFOProduct) -> None:
        """Store a WFO text product."""
        self.set(f"nws:product:{product_id}", product, content_text=product.text or "")

    def get_wfo_product(self, product_id: str) -> WFOProduct | None:
        """Get a cached WFO text product."""
        return self.get(f"nws:product:{product_id}")

    def set_md_list(self, mds: list[MesoscaleDiscussion]) -> None:
        """Store the active MDs list."""
        self.set("spc:list:md_active", mds)

    def get_md_list(self) -> list[MesoscaleDiscussion] | None:
        """Get the cached active MDs list."""
        return self.get("spc:list:md_active")

    def set_watch_list(self, watches: list[Watch]) -> None:
        """Store the active watches list."""
        self.set("spc:list:watch_active", watches)

    def get_watch_list(self) -> list[Watch] | None:
        """Get the cached active watches list."""
        return self.get("spc:list:watch_active")

    def set_wfo_zones(self, wfo_id: str, zones: list[str]) -> None:
        """Store zone list for a WFO."""
        self.set(f"nws:zone:{wfo_id}", zones)

    def get_wfo_zones(self, wfo_id: str) -> list[str] | None:
        """Get cached zone list for a WFO."""
        return self.get(f"nws:zone:{wfo_id}")

    def set_wfo_alerts(self, wfo_id: str, alerts: list[WFOAlert]) -> None:
        """Store alerts for a WFO."""
        self.set(f"nws:list:{wfo_id}:alerts", alerts)

    def get_wfo_alerts(self, wfo_id: str) -> list[WFOAlert] | None:
        """Get cached alerts for a WFO."""
        return self.get(f"nws:list:{wfo_id}:alerts")

    def set_wfo_product_list(
        self,
        wfo_id: str,
        product_type: str,
        products: list[tuple[str, str, str, datetime | None]],
    ) -> None:
        """Store product list for a WFO and product type."""
        self.set(f"nws:list:{wfo_id}:{product_type}", products)

    def get_wfo_product_list(
        self,
        wfo_id: str,
        product_type: str,
    ) -> list[tuple[str, str, str, datetime | None]] | None:
        """Get cached product list for a WFO and product type."""
        return self.get(f"nws:list:{wfo_id}:{product_type}")

    def set_ticker_alerts(self, alerts: list[WFOAlert]) -> None:
        """Store nationwide alerts for ticker."""
        self.set("nws:ticker:nationwide", alerts)

    def get_ticker_alerts(self) -> list[WFOAlert] | None:
        """Get cached nationwide alerts for ticker."""
        return self.get("nws:ticker:nationwide")

    # --- Observation helpers ---

    def set_observation(self, station_id: str, observation: Observation) -> None:
        """Store a weather observation."""
        self.set(f"nws:observation:{station_id.upper()}", observation)

    def get_observation(self, station_id: str) -> Observation | None:
        """Get a cached weather observation."""
        return self.get(f"nws:observation:{station_id.upper()}")

    # === Internal Methods ===

    def _parse_key(self, key: str) -> tuple[str, str, str]:
        """Parse a cache key into components.

        Args:
            key: Cache key in format "source:category:identifier"

        Returns:
            Tuple of (source, category, identifier)
        """
        parts = key.split(":", 2)
        if len(parts) != 3:
            return ("", "", key)
        return (parts[0], parts[1], parts[2])

    def _cleanup_expired(self) -> None:
        """Remove all expired entries."""
        now = time.monotonic()
        expired = [k for k, v in self._cache.items() if now > v.expires_at]
        for key in expired:
            del self._cache[key]
            self._access_order.pop(key, None)

    def _evict_lru(self) -> None:
        """Evict the least recently used entry (O(1) with OrderedDict)."""
        if self._access_order:
            oldest_key, _ = self._access_order.popitem(last=False)
            if oldest_key in self._cache:
                del self._cache[oldest_key]

    def __contains__(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None

    def __len__(self) -> int:
        """Return count of non-expired entries."""
        self._cleanup_expired()
        return len(self._cache)
