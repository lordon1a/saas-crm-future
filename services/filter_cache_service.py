"""Filter cache utilities for advanced contact and company filtering."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class FilterCacheService:
    """Simple in-memory cache for filter query results with TTL support."""

    DEFAULT_TTL = 300  # 5 minutes

    _cache: Dict[str, Dict[str, Any]] = {}
    _lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _cleanup_expired(cls) -> None:
        now = cls._now()
        expired_keys = [
            key
            for key, payload in cls._cache.items()
            if payload.get('expires_at') and payload['expires_at'] <= now
        ]

        for key in expired_keys:
            cls._cache.pop(key, None)

    @classmethod
    def generate_cache_key(
        cls,
        entity_type: str,
        filter_config: Optional[dict],
        workspace_id: int,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> str:
        """Build a deterministic cache key for filter requests."""
        payload = {
            'entity_type': entity_type,
            'workspace_id': workspace_id,
            'filter_config': filter_config or {},
            'page': page,
            'per_page': per_page,
            'sort_by': sort_by,
            'sort_order': sort_order,
        }
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(',', ':'))
        digest = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        return f"filter:{entity_type}:{workspace_id}:{digest}"

    @classmethod
    def get_cached_results(cls, cache_key: str) -> Optional[Tuple[Any, Any]]:
        """Return cached tuple of (results, pagination) if available and not expired."""
        with cls._lock:
            cls._cleanup_expired()
            payload = cls._cache.get(cache_key)
            if not payload:
                return None

            return payload.get('results'), payload.get('pagination')

    @classmethod
    def set_cached_results(
        cls,
        cache_key: str,
        results: Any,
        pagination: Any,
        ttl: Optional[int] = None,
        entity_type: Optional[str] = None,
        workspace_id: Optional[int] = None,
    ) -> None:
        """Store results in cache with TTL and optional metadata."""
        ttl_seconds = ttl if isinstance(ttl, int) and ttl > 0 else cls.DEFAULT_TTL
        expires_at = cls._now() + timedelta(seconds=ttl_seconds)

        with cls._lock:
            cls._cleanup_expired()
            cls._cache[cache_key] = {
                'results': results,
                'pagination': pagination,
                'entity_type': entity_type,
                'workspace_id': workspace_id,
                'expires_at': expires_at,
                'created_at': cls._now(),
            }

    @classmethod
    def invalidate_cache(cls, entity_type: str, workspace_id: int) -> int:
        """Invalidate all cache keys that match entity type and workspace id."""
        with cls._lock:
            cls._cleanup_expired()

            keys_to_remove = [
                key
                for key, payload in cls._cache.items()
                if payload.get('entity_type') == entity_type
                and payload.get('workspace_id') == workspace_id
            ]

            for key in keys_to_remove:
                cls._cache.pop(key, None)

            if keys_to_remove:
                logger.debug(
                    'Invalidated %s filter cache entries for %s:%s',
                    len(keys_to_remove),
                    entity_type,
                    workspace_id,
                )

            return len(keys_to_remove)

    @classmethod
    def clear_all(cls) -> None:
        """Clear all filter cache entries (useful for tests)."""
        with cls._lock:
            cls._cache.clear()

    # Backward-compatible aliases for older callers.
    @classmethod
    def get_cached_result(cls, cache_key: str) -> Optional[Tuple[Any, Any]]:
        return cls.get_cached_results(cache_key)

    @classmethod
    def cache_result(
        cls,
        cache_key: str,
        results: Any,
        pagination: Any = None,
        ttl: Optional[int] = None,
        entity_type: Optional[str] = None,
        workspace_id: Optional[int] = None,
    ) -> None:
        cls.set_cached_results(
            cache_key=cache_key,
            results=results,
            pagination=pagination,
            ttl=ttl,
            entity_type=entity_type,
            workspace_id=workspace_id,
        )
