"""
Caching system for SearchPhone OSINT tool.
Provides file-based caching with TTL support and automatic cleanup.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timedelta

from src.config import CACHE_ENABLED, CACHE_DIR, CACHE_MAX_AGE_DAYS

logger = logging.getLogger(__name__)


def get_cache_key(identifier, source):
    """Generate cache key for an identifier and source"""
    clean = identifier.replace('+', '').replace(' ', '').replace('-', '')
    key = f"{clean}_{source}"
    return hashlib.md5(key.encode()).hexdigest()


def load_from_cache(cache_key):
    """Load cached results if they exist and are not expired"""
    if not CACHE_ENABLED:
        return None
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('timestamp'):
                    cached_time = datetime.fromisoformat(data['timestamp'])
                    if (datetime.now() - cached_time).days < CACHE_MAX_AGE_DAYS:
                        logger.debug(f"Cache hit for {cache_key}")
                        return data.get('data')
                    else:
                        logger.debug(f"Cache expired for {cache_key}")
                else:
                    # Legacy cache without timestamp - still valid
                    return data.get('data')
        except Exception as e:
            logger.warning(f"Failed to load cache for {cache_key}: {e}")
    return None


def save_to_cache(cache_key, data):
    """Save results to cache"""
    if not CACHE_ENABLED:
        return
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    try:
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")


class CacheManager:
    """Manages cache operations with TTL and cleanup"""

    def __init__(self, cache_dir=None, max_age_days=None):
        self.cache_dir = cache_dir or CACHE_DIR
        self.max_age_days = max_age_days or CACHE_MAX_AGE_DAYS

    def get(self, cache_key):
        """Get item from cache"""
        return load_from_cache(cache_key)

    def set(self, cache_key, data):
        """Set item in cache"""
        save_to_cache(cache_key, data)

    def clean_expired(self):
        """Remove all expired cache files"""
        if not os.path.exists(self.cache_dir):
            return 0

        removed = 0
        now = datetime.now()
        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.json'):
                continue
            filepath = os.path.join(self.cache_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get('timestamp'):
                    cached_time = datetime.fromisoformat(data['timestamp'])
                    if (now - cached_time).days >= self.max_age_days:
                        os.remove(filepath)
                        removed += 1
            except (json.JSONDecodeError, KeyError, OSError) as e:
                # Remove corrupted cache files
                try:
                    os.remove(filepath)
                    removed += 1
                except OSError:
                    pass
        return removed

    def clear_all(self):
        """Remove all cache files"""
        if not os.path.exists(self.cache_dir):
            return 0
        removed = 0
        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.json'):
                continue
            filepath = os.path.join(self.cache_dir, filename)
            try:
                os.remove(filepath)
                removed += 1
            except OSError:
                pass
        return removed

    def get_stats(self):
        """Get cache statistics"""
        if not os.path.exists(self.cache_dir):
            return {'total_files': 0, 'total_size_bytes': 0, 'expired_count': 0}

        total_files = 0
        total_size = 0
        expired_count = 0
        now = datetime.now()

        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.json'):
                continue
            filepath = os.path.join(self.cache_dir, filename)
            total_files += 1
            try:
                total_size += os.path.getsize(filepath)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get('timestamp'):
                    cached_time = datetime.fromisoformat(data['timestamp'])
                    if (now - cached_time).days >= self.max_age_days:
                        expired_count += 1
            except Exception:
                expired_count += 1

        return {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'expired_count': expired_count
        }