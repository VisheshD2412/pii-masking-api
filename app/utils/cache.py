"""Thread-safe LRU cache for analysis results."""

import hashlib
import logging
from collections import OrderedDict
from threading import Lock
from typing import List, Optional

from app.config import get_settings
from app.models.requests import DetectedEntity

logger = logging.getLogger(__name__)


class AnalysisCache:
    """
    LRU cache keyed by SHA-256 hash of input text.

    Stores lists of DetectedEntity to avoid repeated Presidio analysis.
    """

    def __init__(self, max_size: int = 1024) -> None:
        """Initialize cache with maximum entry count."""
        self._max_size = max_size
        self._store: OrderedDict[str, List[DetectedEntity]] = OrderedDict()
        self._lock = Lock()

    def _make_key(self, text: str) -> str:
        """Generate cache key from text content."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[List[DetectedEntity]]:
        """Retrieve cached entities for text, or None if not cached."""
        key = self._make_key(text)
        with self._lock:
            if key not in self._store:
                return None
            self._store.move_to_end(key)
            logger.debug("Cache hit for text hash %s...", key[:12])
            return self._store[key]

    def set(self, text: str, entities: List[DetectedEntity]) -> None:
        """Store analysis results for text."""
        key = self._make_key(text)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = entities
            while len(self._store) > self._max_size:
                evicted_key, _ = self._store.popitem(last=False)
                logger.debug("Cache evicted entry %s...", evicted_key[:12])

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._store.clear()

    @property
    def size(self) -> int:
        """Return current number of cached entries."""
        with self._lock:
            return len(self._store)


_settings = get_settings()
analysis_cache = AnalysisCache(max_size=_settings.cache_max_size)
