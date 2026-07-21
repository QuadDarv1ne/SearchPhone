"""
Tests for caching system.
"""

import sys
import os
import tempfile
import json
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cache import get_cache_key, load_from_cache, save_to_cache, CacheManager


def test_get_cache_key():
    """Test cache key generation"""
    key1 = get_cache_key('+79001234567', 'google')
    key2 = get_cache_key('+79001234567', 'google')
    key3 = get_cache_key('+79001234568', 'google')

    # Same input should produce same key
    assert key1 == key2
    # Different input should produce different key
    assert key1 != key3
    # Key should be a 32-character hex string (MD5)
    assert len(key1) == 32
    assert all(c in '0123456789abcdef' for c in key1)


def test_get_cache_key_cleans_number():
    """Test that cache key cleans the phone number"""
    key1 = get_cache_key('+7 900 123-45-67', 'google')
    key2 = get_cache_key('+79001234567', 'google')
    assert key1 == key2


def test_cache_save_and_load():
    """Test saving and loading from cache"""
    # Use a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override CACHE_DIR
        import src.cache as cache_mod
        original_dir = cache_mod.CACHE_DIR
        cache_mod.CACHE_DIR = tmpdir
        cache_mod.CACHE_ENABLED = True

        try:
            key = get_cache_key('+79001234567', 'test')
            data = {'result': 'test_data', 'items': [1, 2, 3]}

            # Save to cache
            save_to_cache(key, data)

            # Load from cache
            loaded = load_from_cache(key)
            assert loaded is not None
            assert loaded['result'] == 'test_data'
            assert loaded['items'] == [1, 2, 3]
        finally:
            cache_mod.CACHE_DIR = original_dir


def test_cache_disabled():
    """Test that cache returns None when disabled"""
    import src.cache as cache_mod
    original = cache_mod.CACHE_ENABLED
    cache_mod.CACHE_ENABLED = False

    try:
        key = get_cache_key('+79001234567', 'test_disabled')
        result = load_from_cache(key)
        assert result is None
    finally:
        cache_mod.CACHE_ENABLED = original


def test_cache_expired():
    """Test that expired cache returns None"""
    with tempfile.TemporaryDirectory() as tmpdir:
        import src.cache as cache_mod
        original_dir = cache_mod.CACHE_DIR
        cache_mod.CACHE_DIR = tmpdir
        cache_mod.CACHE_ENABLED = True

        try:
            key = get_cache_key('+79001234567', 'expired_test')

            # Create expired cache file manually
            cache_file = os.path.join(tmpdir, f"{key}.json")
            old_time = (datetime.now() - timedelta(days=30)).isoformat()
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'timestamp': old_time, 'data': {'old': 'data'}}, f)

            # Should return None because cache is expired
            result = load_from_cache(key)
            assert result is None
        finally:
            cache_mod.CACHE_DIR = original_dir


def test_cache_manager_clear_all():
    """Test CacheManager.clear_all()"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CacheManager(cache_dir=tmpdir)

        # Create some cache files
        for i in range(3):
            key = get_cache_key(f'+7900123456{i}', 'test')
            cache_file = os.path.join(tmpdir, f"{key}.json")
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'timestamp': datetime.now().isoformat(), 'data': {}}, f)

        # Verify files exist
        assert len(os.listdir(tmpdir)) == 3

        # Clear all
        removed = manager.clear_all()
        assert removed == 3
        assert len(os.listdir(tmpdir)) == 0


def test_cache_manager_clean_expired():
    """Test CacheManager.clean_expired()"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CacheManager(cache_dir=tmpdir, max_age_days=7)

        # Create fresh cache file
        fresh_key = get_cache_key('+79001234560', 'fresh')
        fresh_file = os.path.join(tmpdir, f"{fresh_key}.json")
        with open(fresh_file, 'w', encoding='utf-8') as f:
            json.dump({'timestamp': datetime.now().isoformat(), 'data': {}}, f)

        # Create expired cache file
        expired_key = get_cache_key('+79001234561', 'expired')
        expired_file = os.path.join(tmpdir, f"{expired_key}.json")
        old_time = (datetime.now() - timedelta(days=14)).isoformat()
        with open(expired_file, 'w', encoding='utf-8') as f:
            json.dump({'timestamp': old_time, 'data': {}}, f)

        # Clean expired
        removed = manager.clean_expired()
        assert removed == 1

        # Fresh file should still exist
        assert os.path.exists(fresh_file)
        # Expired file should be gone
        assert not os.path.exists(expired_file)


def test_cache_manager_get_stats():
    """Test CacheManager.get_stats()"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CacheManager(cache_dir=tmpdir)

        stats = manager.get_stats()
        assert stats['total_files'] == 0
        assert stats['total_size_bytes'] == 0
        assert stats['expired_count'] == 0