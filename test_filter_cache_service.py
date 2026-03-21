"""
Test script for FilterCacheService
Run with: python test_filter_cache_service.py
"""
from services.filter_cache_service import FilterCacheService

def test_filter_cache_service():
    print("Testing FilterCacheService...")
    
    # Test 1: Generate cache key
    filters = {'filters': [{'field': 'is_starred', 'operator': 'equals', 'value': True}]}
    cache_key = FilterCacheService.generate_cache_key('contact', filters, 1)
    print(f'✓ Test 1: Cache key generated: {cache_key[:16]}...')
    
    # Test 2: Set cached results
    FilterCacheService.set_cached_results(
        cache_key, 
        [{'id': 1, 'name': 'Test'}], 
        {'page': 1, 'total': 1},
        ttl=300,
        entity_type='contact',
        workspace_id=1
    )
    print('✓ Test 2: Cache entry stored')
    
    # Test 3: Get cached results
    results, pagination = FilterCacheService.get_cached_results(cache_key)
    assert results is not None, "Cache should return results"
    assert len(results) == 1, "Should have 1 result"
    assert pagination['page'] == 1, "Page should be 1"
    print(f'✓ Test 3: Cache hit: {len(results)} results, page {pagination["page"]}')
    
    # Test 4: Cache stats
    stats = FilterCacheService.get_cache_stats()
    assert stats['total_entries'] == 1, "Should have 1 cache entry"
    assert stats['active_entries'] == 1, "Should have 1 active entry"
    print(f'✓ Test 4: Cache stats: {stats["total_entries"]} entries, {stats["active_entries"]} active')
    
    # Test 5: Invalidate cache
    invalidated = FilterCacheService.invalidate_cache('contact', 1)
    assert invalidated == 1, "Should invalidate 1 entry"
    print(f'✓ Test 5: Invalidated {invalidated} cache entries')
    
    # Test 6: Verify cache is empty after invalidation
    result = FilterCacheService.get_cached_results(cache_key)
    assert result is None, "Cache should be empty after invalidation"
    print(f'✓ Test 6: Cache miss after invalidation: {result is None}')
    
    # Test 7: Test cleanup_expired
    # Add entry with short TTL
    cache_key2 = FilterCacheService.generate_cache_key('company', filters, 1)
    FilterCacheService.set_cached_results(
        cache_key2,
        [{'id': 2}],
        {'page': 1},
        ttl=0,  # Expires immediately
        entity_type='company',
        workspace_id=1
    )
    import time
    time.sleep(0.1)  # Wait for expiry
    cleaned = FilterCacheService.cleanup_expired()
    assert cleaned == 1, "Should clean 1 expired entry"
    print(f'✓ Test 7: Cleaned up {cleaned} expired entries')
    
    # Test 8: Clear all
    FilterCacheService.set_cached_results(cache_key, [], {}, ttl=300)
    cleared = FilterCacheService.clear_all()
    assert cleared >= 1, "Should clear at least 1 entry"
    print(f'✓ Test 8: Cleared {cleared} cache entries')
    
    print('\n✅ All FilterCacheService tests passed!')

if __name__ == '__main__':
    test_filter_cache_service()
