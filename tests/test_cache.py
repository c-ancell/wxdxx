"""Unit tests for cache module."""

import time
from unittest.mock import patch

import pytest

from wxdxx.cache import (
    DEFAULT_TTLS,
    EMPTY_CONTENT_TTL,
    EMPTY_THRESHOLD,
    ProductCache,
    TTLCache,
)


class TestTTLCache:
    """Tests for the simple TTLCache class."""

    def test_get_set_basic(self) -> None:
        """Basic get/set operations work correctly."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=60.0)
        cache.set("key1", 100)
        assert cache.get("key1") == 100

    def test_get_missing_key_returns_none(self) -> None:
        """Getting a non-existent key returns None."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=60.0)
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self) -> None:
        """Entries expire after TTL."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=0.05)  # 50ms TTL
        cache.set("key1", 100)
        assert cache.get("key1") == 100
        time.sleep(0.06)  # Wait for expiration
        assert cache.get("key1") is None

    def test_custom_ttl_override(self) -> None:
        """Custom TTL on set() overrides default."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=60.0)
        cache.set("key1", 100, ttl=0.05)  # Short TTL
        assert cache.get("key1") == 100
        time.sleep(0.06)
        assert cache.get("key1") is None

    def test_lru_eviction_at_capacity(self) -> None:
        """Oldest entry is evicted when at capacity."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=60.0, max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Cache is now full
        cache.set("d", 4)  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_update_existing_key_no_eviction(self) -> None:
        """Updating an existing key doesn't trigger eviction."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=60.0, max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("a", 10)  # Update, not new key
        assert cache.get("a") == 10
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_invalidate(self) -> None:
        """Invalidate removes specific key."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=60.0)
        cache.set("key1", 100)
        cache.set("key2", 200)
        cache.invalidate("key1")
        assert cache.get("key1") is None
        assert cache.get("key2") == 200

    def test_invalidate_missing_key(self) -> None:
        """Invalidating a missing key doesn't raise."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=60.0)
        cache.invalidate("nonexistent")  # Should not raise

    def test_clear(self) -> None:
        """Clear removes all entries."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=60.0)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_contains(self) -> None:
        """__contains__ checks for valid entries."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=60.0)
        cache.set("key1", 100)
        assert "key1" in cache
        assert "nonexistent" not in cache

    def test_contains_expired(self) -> None:
        """__contains__ returns False for expired entries."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=0.05)
        cache.set("key1", 100)
        assert "key1" in cache
        time.sleep(0.06)
        assert "key1" not in cache

    def test_len(self) -> None:
        """__len__ returns count of non-expired entries."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=60.0)
        cache.set("a", 1)
        cache.set("b", 2)
        assert len(cache) == 2

    def test_len_excludes_expired(self) -> None:
        """__len__ excludes expired entries."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=0.05)
        cache.set("a", 1)
        cache.set("b", 2, ttl=60.0)  # Long TTL
        time.sleep(0.06)
        assert len(cache) == 1  # Only "b" remains

    def test_cleanup_expired(self) -> None:
        """cleanup_expired removes all expired entries."""
        cache: TTLCache[str, int] = TTLCache(default_ttl=0.05)
        cache.set("a", 1)
        cache.set("b", 2, ttl=60.0)
        time.sleep(0.06)
        cache.cleanup_expired()
        assert len(cache._cache) == 1  # Only "b" in internal dict


class TestProductCache:
    """Tests for the unified ProductCache class."""

    # === Core CRUD Operations ===

    def test_get_set_basic(self) -> None:
        """Basic get/set with structured keys."""
        cache = ProductCache()
        cache.set("spc:md:2462", {"number": 2462, "text": "test"})
        assert cache.get("spc:md:2462") == {"number": 2462, "text": "test"}

    def test_get_missing_key(self) -> None:
        """Getting a non-existent key returns None."""
        cache = ProductCache()
        assert cache.get("spc:md:9999") is None

    def test_key_parsing(self) -> None:
        """Keys are parsed correctly into components."""
        cache = ProductCache()
        cache.set("spc:md:2462", "test")
        entry = cache.get_entry("spc:md:2462")
        assert entry is not None
        assert entry.source == "spc"
        assert entry.category == "md"
        assert entry.identifier == "2462"

    def test_key_with_colons_in_identifier(self) -> None:
        """Keys with colons in identifier are handled."""
        cache = ProductCache()
        cache.set("nws:list:OUN:AFD", ["product1", "product2"])
        entry = cache.get_entry("nws:list:OUN:AFD")
        assert entry is not None
        assert entry.source == "nws"
        assert entry.category == "list"
        assert entry.identifier == "OUN:AFD"

    # === TTL Behavior ===

    def test_category_based_ttl(self) -> None:
        """Different categories get different TTLs."""
        cache = ProductCache()
        cache.set("spc:outlook:day1", "outlook text")
        cache.set("nws:ticker:nationwide", "ticker data")

        outlook_entry = cache.get_entry("spc:outlook:day1")
        ticker_entry = cache.get_entry("nws:ticker:nationwide")

        assert outlook_entry is not None
        assert ticker_entry is not None

        # Outlook TTL should be longer than ticker TTL
        outlook_ttl = outlook_entry.expires_at - outlook_entry.created_at
        ticker_ttl = ticker_entry.expires_at - ticker_entry.created_at

        assert outlook_ttl == pytest.approx(DEFAULT_TTLS["outlook"], rel=0.1)
        assert ticker_ttl == pytest.approx(DEFAULT_TTLS["ticker"], rel=0.1)

    def test_custom_ttl_override(self) -> None:
        """Custom TTL overrides category default."""
        cache = ProductCache()
        cache.set("spc:md:2462", "test", ttl=10.0)
        entry = cache.get_entry("spc:md:2462")
        assert entry is not None
        actual_ttl = entry.expires_at - entry.created_at
        assert actual_ttl == pytest.approx(10.0, rel=0.1)

    def test_ttl_expiration(self) -> None:
        """Entries expire after TTL."""
        cache = ProductCache()
        cache.set("spc:md:2462", "test", ttl=0.05)
        assert cache.get("spc:md:2462") == "test"
        time.sleep(0.06)
        assert cache.get("spc:md:2462") is None

    # === Empty Content Detection ===

    def test_empty_content_short_ttl(self) -> None:
        """Empty content gets shorter TTL."""
        cache = ProductCache()
        short_text = "x" * 50  # Below EMPTY_THRESHOLD (100)
        cache.set("spc:md:2462", "test", content_text=short_text)

        entry = cache.get_entry("spc:md:2462")
        assert entry is not None
        assert entry.is_empty is True
        actual_ttl = entry.expires_at - entry.created_at
        assert actual_ttl == pytest.approx(EMPTY_CONTENT_TTL, rel=0.1)

    def test_populated_content_normal_ttl(self) -> None:
        """Populated content gets normal category TTL."""
        cache = ProductCache()
        long_text = "x" * 200  # Above EMPTY_THRESHOLD
        cache.set("spc:md:2462", "test", content_text=long_text)

        entry = cache.get_entry("spc:md:2462")
        assert entry is not None
        assert entry.is_empty is False
        actual_ttl = entry.expires_at - entry.created_at
        assert actual_ttl == pytest.approx(DEFAULT_TTLS["md"], rel=0.1)

    def test_is_empty(self) -> None:
        """is_empty correctly identifies empty content."""
        cache = ProductCache()
        cache.set("spc:md:1", "test", content_text="short")
        cache.set("spc:md:2", "test", content_text="x" * 200)

        assert cache.is_empty("spc:md:1") is True
        assert cache.is_empty("spc:md:2") is False
        assert cache.is_empty("nonexistent") is False

    def test_get_empty_products(self) -> None:
        """get_empty_products returns all empty entries."""
        cache = ProductCache()
        cache.set("spc:md:1", "test", content_text="short")
        cache.set("spc:md:2", "test", content_text="x" * 200)
        cache.set("spc:md:3", "test", content_text="tiny")

        empty = cache.get_empty_products()
        assert "spc:md:1" in empty
        assert "spc:md:3" in empty
        assert "spc:md:2" not in empty

    def test_mark_populated_extends_ttl(self) -> None:
        """mark_populated extends TTL for previously empty entries."""
        cache = ProductCache()
        cache.set("spc:md:2462", "test", content_text="short")

        entry_before = cache.get_entry("spc:md:2462")
        assert entry_before is not None
        assert entry_before.is_empty is True
        expires_before = entry_before.expires_at

        # Mark as populated with long content
        cache.mark_populated("spc:md:2462", "x" * 200)

        entry_after = cache.get_entry("spc:md:2462")
        assert entry_after is not None
        assert entry_after.is_empty is False
        assert entry_after.expires_at > expires_before

    # === LRU Eviction ===

    def test_lru_eviction_at_capacity(self) -> None:
        """Least recently used entry is evicted at capacity."""
        cache = ProductCache(max_size=3)
        cache.set("spc:md:1", "test1")
        cache.set("spc:md:2", "test2")
        cache.set("spc:md:3", "test3")

        # Access md:1 to make it recently used
        cache.get("spc:md:1")

        # Add new entry, should evict md:2 (least recently used)
        cache.set("spc:md:4", "test4")

        assert cache.get("spc:md:1") == "test1"  # Recently accessed
        assert cache.get("spc:md:2") is None  # Evicted
        assert cache.get("spc:md:3") == "test3"
        assert cache.get("spc:md:4") == "test4"

    def test_update_existing_no_eviction(self) -> None:
        """Updating existing key doesn't trigger eviction."""
        cache = ProductCache(max_size=3)
        cache.set("spc:md:1", "test1")
        cache.set("spc:md:2", "test2")
        cache.set("spc:md:3", "test3")

        cache.set("spc:md:1", "updated")  # Update, not new

        assert cache.get("spc:md:1") == "updated"
        assert cache.get("spc:md:2") == "test2"
        assert cache.get("spc:md:3") == "test3"

    # === Targeted Invalidation ===

    def test_invalidate_single_key(self) -> None:
        """Invalidate removes specific key."""
        cache = ProductCache()
        cache.set("spc:md:1", "test1")
        cache.set("spc:md:2", "test2")

        result = cache.invalidate("spc:md:1")

        assert result is True
        assert cache.get("spc:md:1") is None
        assert cache.get("spc:md:2") == "test2"

    def test_invalidate_missing_key(self) -> None:
        """Invalidating missing key returns False."""
        cache = ProductCache()
        result = cache.invalidate("nonexistent")
        assert result is False

    def test_invalidate_by_source(self) -> None:
        """Invalidate all entries from a source."""
        cache = ProductCache()
        cache.set("spc:md:1", "test1")
        cache.set("spc:watch:100", "test2")
        cache.set("nws:alert:abc", "test3")

        count = cache.invalidate_by_source("spc")

        assert count == 2
        assert cache.get("spc:md:1") is None
        assert cache.get("spc:watch:100") is None
        assert cache.get("nws:alert:abc") == "test3"

    def test_invalidate_by_category(self) -> None:
        """Invalidate all entries of a category."""
        cache = ProductCache()
        cache.set("spc:md:1", "test1")
        cache.set("spc:md:2", "test2")
        cache.set("spc:watch:100", "test3")

        count = cache.invalidate_by_category("md")

        assert count == 2
        assert cache.get("spc:md:1") is None
        assert cache.get("spc:md:2") is None
        assert cache.get("spc:watch:100") == "test3"

    def test_invalidate_by_pattern_source_and_category(self) -> None:
        """Invalidate by source and category pattern."""
        cache = ProductCache()
        cache.set("spc:md:1", "test1")
        cache.set("spc:watch:100", "test2")
        cache.set("nws:md:abc", "test3")

        count = cache.invalidate_by_pattern(source="spc", category="md")

        assert count == 1
        assert cache.get("spc:md:1") is None
        assert cache.get("spc:watch:100") == "test2"
        assert cache.get("nws:md:abc") == "test3"

    def test_invalidate_by_pattern_identifier_prefix(self) -> None:
        """Invalidate by identifier prefix."""
        cache = ProductCache()
        cache.set("nws:list:OUN:AFD", "test1")
        cache.set("nws:list:OUN:HWO", "test2")
        cache.set("nws:list:DFW:AFD", "test3")

        count = cache.invalidate_by_pattern(source="nws", identifier_prefix="OUN")

        assert count == 2
        assert cache.get("nws:list:OUN:AFD") is None
        assert cache.get("nws:list:OUN:HWO") is None
        assert cache.get("nws:list:DFW:AFD") == "test3"

    def test_clear(self) -> None:
        """Clear removes all entries."""
        cache = ProductCache()
        cache.set("spc:md:1", "test1")
        cache.set("nws:alert:abc", "test2")

        cache.clear()

        assert len(cache) == 0
        assert cache.get("spc:md:1") is None
        assert cache.get("nws:alert:abc") is None

    # === Staleness Tracking ===

    def test_get_age(self) -> None:
        """get_age returns seconds since creation."""
        cache = ProductCache()
        cache.set("spc:md:1", "test")
        time.sleep(0.05)

        age = cache.get_age("spc:md:1")
        assert age is not None
        assert age >= 0.05

    def test_get_age_missing_key(self) -> None:
        """get_age returns None for missing key."""
        cache = ProductCache()
        assert cache.get_age("nonexistent") is None

    def test_get_time_to_expiry(self) -> None:
        """get_time_to_expiry returns seconds until expiry."""
        cache = ProductCache()
        cache.set("spc:md:1", "test", ttl=1.0)

        tte = cache.get_time_to_expiry("spc:md:1")
        assert tte is not None
        assert 0.9 <= tte <= 1.0

    def test_get_time_to_expiry_expired(self) -> None:
        """get_time_to_expiry returns None for expired entry."""
        cache = ProductCache()
        cache.set("spc:md:1", "test", ttl=0.05)
        time.sleep(0.06)

        assert cache.get_time_to_expiry("spc:md:1") is None

    def test_get_stale_products(self) -> None:
        """get_stale_products returns entries older than threshold."""
        cache = ProductCache()
        cache.set("spc:md:1", "test", ttl=60.0)
        time.sleep(0.05)
        cache.set("spc:md:2", "test", ttl=60.0)

        stale = cache.get_stale_products(max_age=0.03)
        assert "spc:md:1" in stale
        assert "spc:md:2" not in stale

    # === Statistics ===

    def test_stats(self) -> None:
        """stats returns correct cache statistics."""
        cache = ProductCache()
        cache.set("spc:md:1", "test", content_text="short")
        cache.set("spc:watch:100", "test", content_text="x" * 200)
        cache.set("nws:alert:abc", "test", content_text="x" * 200)

        stats = cache.stats()

        assert stats["total_entries"] == 3
        assert stats["by_source"]["spc"] == 2
        assert stats["by_source"]["nws"] == 1
        assert stats["by_category"]["md"] == 1
        assert stats["by_category"]["watch"] == 1
        assert stats["by_category"]["alert"] == 1
        assert stats["empty_count"] == 1

    # === Container Protocol ===

    def test_contains(self) -> None:
        """__contains__ checks for valid entries."""
        cache = ProductCache()
        cache.set("spc:md:1", "test")

        assert "spc:md:1" in cache
        assert "nonexistent" not in cache

    def test_len(self) -> None:
        """__len__ returns count of non-expired entries."""
        cache = ProductCache()
        cache.set("spc:md:1", "test")
        cache.set("spc:md:2", "test")

        assert len(cache) == 2

    def test_len_excludes_expired(self) -> None:
        """__len__ excludes expired entries."""
        cache = ProductCache()
        cache.set("spc:md:1", "test", ttl=0.05)
        cache.set("spc:md:2", "test", ttl=60.0)
        time.sleep(0.06)

        assert len(cache) == 1
