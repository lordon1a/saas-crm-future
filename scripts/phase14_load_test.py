"""
Phase 14 lightweight load test script.

Usage:
  python scripts/phase14_load_test.py --base-url http://127.0.0.1:5000 --token YOUR_SESSION_COOKIE --requests 150 --workers 15

Notes:
- This script targets read-heavy endpoints to validate baseline response under concurrent load.
- It expects an authenticated session cookie value (the `session` cookie).
"""
import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

ENDPOINTS = [
    '/api/conversations',
    '/api/analytics/dashboard',
    '/api/v1/contacts',
    '/api/v1/deals',
    '/api/collaboration/notifications/unread-count',
]


def run_single(base_url, session_cookie):
    url = base_url.rstrip('/') + ENDPOINTS[int(time.time() * 1000) % len(ENDPOINTS)]
    start = time.perf_counter()
    try:
        res = requests.get(url, cookies={'session': session_cookie}, timeout=15)
        elapsed = (time.perf_counter() - start) * 1000
        return res.status_code, elapsed
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        return 0, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--token', required=True, help='Flask session cookie value')
    parser.add_argument('--requests', type=int, default=150)
    parser.add_argument('--workers', type=int, default=15)
    args = parser.parse_args()

    latencies = []
    codes = {}

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(run_single, args.base_url, args.token) for _ in range(args.requests)]
        for f in as_completed(futures):
            code, latency = f.result()
            latencies.append(latency)
            codes[code] = codes.get(code, 0) + 1
    total = time.perf_counter() - start

    if latencies:
        p95 = sorted(latencies)[int(len(latencies) * 0.95) - 1]
        p99 = sorted(latencies)[int(len(latencies) * 0.99) - 1]
    else:
        p95 = p99 = 0

    print('Load test summary')
    print('-----------------')
    print(f'total_requests={args.requests}')
    print(f'workers={args.workers}')
    print(f'total_time_sec={total:.2f}')
    print(f'rps={args.requests / total:.2f}')
    print(f'latency_avg_ms={statistics.mean(latencies):.2f}' if latencies else 'latency_avg_ms=0')
    print(f'latency_p95_ms={p95:.2f}')
    print(f'latency_p99_ms={p99:.2f}')
    print(f'status_codes={codes}')


if __name__ == '__main__':
    main()
