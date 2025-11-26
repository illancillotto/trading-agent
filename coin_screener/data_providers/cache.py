"""
Caching layer for screening data
"""
import json
import logging
import pickle
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)


class DataCache:
    """Simple file-based cache with expiration"""

    def __init__(self, cache_dir: str = ".cache/screener"):
        """
        Initialize cache.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized DataCache at {self.cache_dir}")

    def get(self, key: str, max_age_seconds: int = 3600) -> Optional[Any]:
        """
        Get cached value if it exists and is not expired.

        Args:
            key: Cache key
            max_age_seconds: Maximum age in seconds before expiration

        Returns:
            Cached value or None if not found/expired
        """
        cache_file = self._get_cache_file(key)

        if not cache_file.exists():
            return None

        try:
            # Check file age
            file_mtime = cache_file.stat().st_mtime
            file_age = datetime.now().timestamp() - file_mtime

            if file_age > max_age_seconds:
                logger.debug(f"Cache expired for key '{key}' (age: {file_age:.0f}s)")
                cache_file.unlink()  # Delete expired cache
                return None

            # Load cached data
            with open(cache_file, "rb") as f:
                data = pickle.load(f)

            logger.debug(f"Cache hit for key '{key}'")
            return data

        except Exception as e:
            logger.warning(f"Error reading cache for key '{key}': {e}")
            return None

    def set(self, key: str, value: Any) -> bool:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be picklable)

        Returns:
            True if successful
        """
        cache_file = self._get_cache_file(key)

        try:
            with open(cache_file, "wb") as f:
                pickle.dump(value, f)

            logger.debug(f"Cached data for key '{key}'")
            return True

        except Exception as e:
            logger.error(f"Error writing cache for key '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete cached value.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        cache_file = self._get_cache_file(key)

        if cache_file.exists():
            try:
                cache_file.unlink()
                logger.debug(f"Deleted cache for key '{key}'")
                return True
            except Exception as e:
                logger.error(f"Error deleting cache for key '{key}': {e}")
                return False

        return False

    def clear(self) -> int:
        """
        Clear all cached files.

        Returns:
            Number of files deleted
        """
        count = 0
        try:
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
                count += 1

            logger.info(f"Cleared {count} cache files")
            return count

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return count

    def clear_expired(self, max_age_seconds: int = 86400) -> int:
        """
        Clear expired cache files.

        Args:
            max_age_seconds: Maximum age to keep

        Returns:
            Number of files deleted
        """
        count = 0
        now = datetime.now().timestamp()

        try:
            for cache_file in self.cache_dir.glob("*.pkl"):
                file_age = now - cache_file.stat().st_mtime

                if file_age > max_age_seconds:
                    cache_file.unlink()
                    count += 1

            if count > 0:
                logger.info(f"Cleared {count} expired cache files")

            return count

        except Exception as e:
            logger.error(f"Error clearing expired cache: {e}")
            return count

    def _get_cache_file(self, key: str) -> Path:
        """
        Get cache file path for a key.

        Args:
            key: Cache key

        Returns:
            Path to cache file
        """
        # Sanitize key for filename
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe_key}.pkl"

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        try:
            cache_files = list(self.cache_dir.glob("*.pkl"))
            total_size = sum(f.stat().st_size for f in cache_files)
            now = datetime.now().timestamp()

            ages = [now - f.stat().st_mtime for f in cache_files]
            avg_age = sum(ages) / len(ages) if ages else 0

            return {
                "total_files": len(cache_files),
                "total_size_mb": total_size / (1024 * 1024),
                "avg_age_hours": avg_age / 3600,
                "cache_dir": str(self.cache_dir)
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
