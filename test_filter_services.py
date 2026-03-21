#!/usr/bin/env python3
"""
Service Layer Test Script
Tests FilterService and SavedFilterService basic functionality
"""

from app import app, db
from models_crm import Contact, Company, SavedFilter, UserDefinedFilter, FilterExecutionLog
from services.filter_service import FilterService, FILTER_OPERATORS, QUICK_FILTERS
from services.saved_filter_service import SavedFilterService
from datetime import datetime, timedelta

def test_filter_operators():
    """Test FILTER_OPERATORS dictionary"""
    print("\n=== Testing FILTER_OPERATORS ===")
    print(f"✓ Total operators: {len(FILTER_OPERATORS)}")
    print(f"✓ Operators: {', '.join(FILTER_OPERATORS.keys())}")
    assert 'equals' in FILTER_OPERATORS
    assert 'contains' in FILTER_OPERATORS
    assert 'greater_than' in FILTER_OPERATORS
    print("✓ FILTER_OPERATORS OK")

def test_quick_filters():
    """Test QUICK_FILTERS dictionary"""
    print("\n=== Testing QUICK_FILTERS ===")
    print(f"✓ Contact quick filters: {len(QUICK_FILTERS.get('contact', {}))}")
    print(f"✓ Company quick filters: {len(QUICK_FILTERS.get('company', {}))}")
    assert 'contact' in QUICK_FILTERS
    assert 'company' in QUICK_FILTERS
    print("✓ QUICK_FILTERS OK")

def test_validate_filters():
    """Test FilterService.validate_filters()"""
    print("\n=== Testing validate_filters() ===")
    
    # Valid filter
    valid_filter = {
        'filters': [
            {'field': 'first_name', 'operator': 'contains', 'value': 'test'}
        ]
    }
    is_valid, error = FilterService.validate_filters(valid_filter, 'contact')
    print(f"✓ Valid filter: is_valid={is_valid}, error={error}")
    assert is_valid == True
    
    # Invalid operator
    invalid_filter = {
        'filters': [
            {'field': 'first_name', 'operator': 'invalid_op', 'value': 'test'}
        ]
    }
    is_valid, error = FilterService.validate_filters(invalid_filter, 'contact')
    print(f"✓ Invalid operator: is_valid={is_valid}, error={error}")
    assert is_valid == False
    
    # Missing field
    missing_field = {
        'filters': [
            {'operator': 'equals', 'value': 'test'}
        ]
    }
    is_valid, error = FilterService.validate_filters(missing_field, 'contact')
    print(f"✓ Missing field: is_valid={is_valid}, error={error}")
    assert is_valid == False
    
    print("✓ validate_filters() OK")

def test_evaluate_quick_filter():
    """Test FilterService.evaluate_quick_filter()"""
    print("\n=== Testing evaluate_quick_filter() ===")
    
    # Test contact quick filter
    config = FilterService.evaluate_quick_filter('starred', 'contact')
    print(f"✓ starred config: {config}")
    assert 'filters' in config
    assert len(config['filters']) > 0
    
    # Test company quick filter
    config = FilterService.evaluate_quick_filter('no_parent', 'company')
    print(f"✓ no_parent config: {config}")
    assert 'filters' in config
    
    # Test dynamic date filter
    config = FilterService.evaluate_quick_filter('created_this_week', 'contact')
    print(f"✓ created_this_week config: {config}")
    assert 'filters' in config
    # Check that WEEK_START was replaced with actual date
    assert config['filters'][0]['value'] != 'WEEK_START'
    
    print("✓ evaluate_quick_filter() OK")

def test_saved_filter_service():
    """Test SavedFilterService basic functionality"""
    print("\n=== Testing SavedFilterService ===")
    
    with app.app_context():
        # Check if SavedFilter table exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"✓ Total database tables: {len(tables)}")
        
        # Check for filter-related tables
        filter_tables = [t for t in tables if 'filter' in t]
        print(f"✓ Filter-related tables: {', '.join(filter_tables)}")
        
        assert 'saved_filters' in tables, "saved_filters table not found"
        assert 'user_defined_filters' in tables, "user_defined_filters table not found"
        assert 'filter_execution_logs' in tables, "filter_execution_logs table not found"
        
        print("✓ SavedFilterService tables OK")

def test_cache_functionality():
    """Test SavedFilterService cache"""
    print("\n=== Testing Cache Functionality ===")
    
    # Test cache miss
    result = SavedFilterService.get_cached_results(999, workspace_id=1)
    print(f"✓ Cache miss: {result}")
    assert result is None
    
    # Test cache set and get
    test_results = [{'id': 1, 'name': 'Test'}]
    SavedFilterService.set_cached_results(999, workspace_id=1, results=test_results)
    cached = SavedFilterService.get_cached_results(999, workspace_id=1)
    print(f"✓ Cache hit: {cached}")
    assert cached == test_results
    
    # Test workspace isolation
    cached_wrong_workspace = SavedFilterService.get_cached_results(999, workspace_id=2)
    print(f"✓ Workspace isolation: {cached_wrong_workspace}")
    assert cached_wrong_workspace is None
    
    print("✓ Cache functionality OK")

def main():
    """Run all tests"""
    print("=" * 60)
    print("FILTER SERVICE LAYER TEST")
    print("=" * 60)
    
    try:
        test_filter_operators()
        test_quick_filters()
        test_validate_filters()
        test_evaluate_quick_filter()
        test_saved_filter_service()
        test_cache_functionality()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
