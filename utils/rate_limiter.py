"""Lightweight in-memory rate limiter for advanced filter endpoints."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Deque, Dict, Tuple

from flask import jsonify, request, session

# Default policy: 60 filter requests per 60-second window per user key.
MAX_REQUESTS = 60
WINDOW_SECONDS = 60

_lock = threading.RLock()
_request_windows: Dict[str, Deque[float]] = defaultdict(deque)


def _build_key(user_id) -> str:
    if user_id is not None:
        return f'user:{user_id}'

    workspace_id = session.get('workspace_id')
    if workspace_id is not None:
        return f'workspace:{workspace_id}'

    remote = request.remote_addr or 'unknown'
    return f'ip:{remote}'


def _cleanup_window(entries: Deque[float], now_ts: float, window_seconds: int) -> None:
    cutoff = now_ts - window_seconds
    while entries and entries[0] <= cutoff:
        entries.popleft()


def get_rate_limit_status(user_id, max_requests: int = MAX_REQUESTS, window_seconds: int = WINDOW_SECONDS) -> Tuple[int, int, int]:
    """
    Return current request count, max allowed, and window size.

    This call also consumes one slot when below limit so callers can use
    a simple pre-check pattern.
    """
    key = _build_key(user_id)
    now_ts = time.time()

    with _lock:
        entries = _request_windows[key]
        _cleanup_window(entries, now_ts, window_seconds)
        current_count = len(entries)

        # Consume a slot only if request is still within allowed range.
        if current_count < max_requests:
            entries.append(now_ts)

        return current_count, max_requests, window_seconds


def filter_rate_limit(max_requests: int = MAX_REQUESTS, window_seconds: int = WINDOW_SECONDS):
    """Decorator for rate limiting advanced filter API endpoints."""

    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            user_id = session.get('user_id')
            current_count, limit, window = get_rate_limit_status(
                user_id=user_id,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )

            if current_count >= limit:
                response = jsonify(
                    {
                        'error': f'Rate limit exceeded. Maximum {limit} filter requests allowed per {window} seconds.',
                        'retry_after': window,
                    }
                )
                response.headers['Retry-After'] = str(window)
                return response, 429

            return func(*args, **kwargs)

        return wrapped

    return decorator


def clear_rate_limiter_state() -> None:
    """Clear all in-memory buckets (primarily useful for tests)."""
    with _lock:
        _request_windows.clear()
