"""
Saved Filters API Routes
Handles CRUD operations for saved filter configurations
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
from models_crm import SavedFilter
from models import User, db
from datetime import datetime
import json

filters_bp = Blueprint('filters', __name__, url_prefix='/api/v1')


def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


@filters_bp.route('/saved-filters', methods=['GET'])
@login_required
def get_saved_filters():
    """
    Get user's saved filters + shared team filters
    Query params: entity_type (required)
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        entity_type = request.args.get('entity_type')
        
        if not entity_type:
            return jsonify({'error': 'entity_type parameter is required'}), 400
        
        if entity_type not in ['contact', 'company']:
            return jsonify({'error': 'Invalid entity_type. Must be contact or company'}), 400
        
        # Get user's own filters
        user_filters = SavedFilter.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            entity_type=entity_type
        ).order_by(SavedFilter.updated_at.desc()).all()
        
        # Get shared team filters (excluding user's own shared filters)
        shared_filters = SavedFilter.query.filter(
            SavedFilter.workspace_id == workspace_id,
            SavedFilter.entity_type == entity_type,
            SavedFilter.is_shared == True,
            SavedFilter.user_id != user_id
        ).order_by(SavedFilter.updated_at.desc()).all()
        
        # Format response
        def format_filter(f):
            creator = User.query.get(f.user_id)
            return {
                'id': f.id,
                'name': f.name,
                'description': f.description,
                'entity_type': f.entity_type,
                'filter_config': json.loads(f.filter_config),
                'is_shared': f.is_shared,
                'is_owner': f.user_id == user_id,
                'creator_name': f'{creator.first_name} {creator.last_name}' if creator else 'Unknown',
                'created_at': f.created_at.isoformat(),
                'updated_at': f.updated_at.isoformat()
            }
        
        return jsonify({
            'user_filters': [format_filter(f) for f in user_filters],
            'shared_filters': [format_filter(f) for f in shared_filters]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@filters_bp.route('/saved-filters', methods=['POST'])
@login_required
def create_saved_filter():
    """
    Create new saved filter
    Request body: name, entity_type, filter_config, is_shared (optional)
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        data = request.get_json()
        
        # Validation
        if not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        
        if not data.get('entity_type'):
            return jsonify({'error': 'entity_type is required'}), 400
        
        if data['entity_type'] not in ['contact', 'company']:
            return jsonify({'error': 'Invalid entity_type'}), 400
        
        if not data.get('filter_config'):
            return jsonify({'error': 'filter_config is required'}), 400
        
        # Check filter limit (50 per user per entity_type)
        existing_count = SavedFilter.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            entity_type=data['entity_type']
        ).count()
        
        if existing_count >= 50:
            return jsonify({'error': 'Filter limit reached (50 per entity type)'}), 400
        
        # Create filter
        new_filter = SavedFilter(
            workspace_id=workspace_id,
            user_id=user_id,
            name=data['name'],
            description=data.get('description'),
            entity_type=data['entity_type'],
            filter_config=json.dumps(data['filter_config']),
            is_shared=data.get('is_shared', False)
        )
        
        db.session.add(new_filter)
        db.session.commit()
        
        return jsonify({
            'id': new_filter.id,
            'name': new_filter.name,
            'message': 'Filter created successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@filters_bp.route('/saved-filters/<int:filter_id>', methods=['PATCH'])
@login_required
def update_saved_filter(filter_id):
    """
    Update saved filter (only owner)
    Request body: name, filter_config, is_shared (all optional)
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        # Get filter
        saved_filter = SavedFilter.query.filter_by(
            id=filter_id,
            workspace_id=workspace_id
        ).first()
        
        if not saved_filter:
            return jsonify({'error': 'Filter not found'}), 404
        
        # Check ownership
        if saved_filter.user_id != user_id:
            return jsonify({'error': 'Permission denied. Only owner can edit'}), 403
        
        # Update fields
        data = request.get_json()
        
        if 'name' in data:
            saved_filter.name = data['name']
        
        if 'description' in data:
            saved_filter.description = data['description']
        
        if 'filter_config' in data:
            saved_filter.filter_config = json.dumps(data['filter_config'])
        
        if 'is_shared' in data:
            saved_filter.is_shared = data['is_shared']
        
        saved_filter.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'id': saved_filter.id,
            'message': 'Filter updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@filters_bp.route('/saved-filters/<int:filter_id>', methods=['DELETE'])
@login_required
def delete_saved_filter(filter_id):
    """
    Delete saved filter (only owner)
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        # Get filter
        saved_filter = SavedFilter.query.filter_by(
            id=filter_id,
            workspace_id=workspace_id
        ).first()
        
        if not saved_filter:
            return jsonify({'error': 'Filter not found'}), 404
        
        # Check ownership
        if saved_filter.user_id != user_id:
            return jsonify({'error': 'Permission denied. Only owner can delete'}), 403
        
        db.session.delete(saved_filter)
        db.session.commit()
        
        return jsonify({'message': 'Filter deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@filters_bp.route('/saved-filters/<int:filter_id>/duplicate', methods=['POST'])
@login_required
def duplicate_saved_filter(filter_id):
    """
    Duplicate shared filter to user's own filters
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        # Get original filter
        original_filter = SavedFilter.query.filter_by(
            id=filter_id,
            workspace_id=workspace_id
        ).first()
        
        if not original_filter:
            return jsonify({'error': 'Filter not found'}), 404
        
        # Check if it's a shared filter
        if not original_filter.is_shared:
            return jsonify({'error': 'Only shared filters can be duplicated'}), 400
        
        # Check filter limit
        existing_count = SavedFilter.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
            entity_type=original_filter.entity_type
        ).count()
        
        if existing_count >= 50:
            return jsonify({'error': 'Filter limit reached (50 per entity type)'}), 400
        
        # Create duplicate
        duplicate_filter = SavedFilter(
            workspace_id=workspace_id,
            user_id=user_id,
            name=f"{original_filter.name} (Copy)",
            entity_type=original_filter.entity_type,
            filter_config=original_filter.filter_config,
            is_shared=False  # User's copy is not shared by default
        )
        
        db.session.add(duplicate_filter)
        db.session.commit()
        
        return jsonify({
            'id': duplicate_filter.id,
            'name': duplicate_filter.name,
            'message': 'Filter duplicated successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@filters_bp.route('/filters/preview-count', methods=['POST'])
@login_required
def get_filter_preview_count():
    """
    Get preview count for filter configuration (with caching)
    Request body: entity_type, filters
    Returns: count of results that would match the filter
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        data = request.get_json()
        
        # Validation
        if not data.get('entity_type'):
            return jsonify({'error': 'entity_type is required'}), 400
        
        if data['entity_type'] not in ['contact', 'company']:
            return jsonify({'error': 'Invalid entity_type'}), 400
        
        if not data.get('filters'):
            return jsonify({'error': 'filters is required'}), 400
        
        entity_type = data['entity_type']
        filters = data['filters']
        
        # Import services
        from services.filter_service import FilterService
        from services.filter_cache_service import FilterCacheService
        
        # Generate cache key for preview count (different from query results cache)
        cache_params = {
            'filters': filters,
            'preview_count': True  # Distinguish from regular query cache
        }
        cache_key = FilterCacheService.generate_cache_key(entity_type, cache_params, workspace_id)
        
        # Try to get cached count
        cached_data = FilterCacheService.get_cached_results(cache_key)
        if cached_data is not None:
            count, _ = cached_data
            return jsonify({
                'count': count,
                'from_cache': True
            }), 200
        
        # Get model
        from models_crm import Contact, Company
        model = Contact if entity_type == 'contact' else Company
        
        # Build query with workspace isolation
        base_query = db.query(model).filter(
            model.workspace_id == workspace_id,
            model.is_deleted == False
        )
        
        # Apply filters
        base_query = FilterService.build_query(base_query, {'filters': filters}, entity_type)
        
        # Get count
        count = base_query.count()
        
        # Cache the count with shorter TTL (30 seconds)
        FilterCacheService.set_cached_results(
            cache_key,
            count,
            {},
            ttl=FilterCacheService.PREVIEW_COUNT_TTL,
            entity_type=entity_type,
            workspace_id=workspace_id
        )
        
        return jsonify({
            'count': count,
            'from_cache': False
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@filters_bp.route('/admin/filter-stats', methods=['GET'])
@login_required
def get_filter_stats():
    """
    Get filter execution statistics (admin only)
    Query params: 
    - entity_type (optional): filter by entity type
    - days (optional): number of days to look back (default: 7)
    Returns: statistics about filter executions including slow queries
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        # Get query parameters
        entity_type = request.args.get('entity_type')
        days = int(request.args.get('days', 7))
        
        # Import models
        from models_crm import FilterExecutionLog
        from datetime import timedelta
        
        # Build query
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = FilterExecutionLog.query.filter(
            FilterExecutionLog.workspace_id == workspace_id,
            FilterExecutionLog.created_at >= cutoff_date
        )
        
        if entity_type:
            if entity_type not in ['contact', 'company']:
                return jsonify({'error': 'Invalid entity_type'}), 400
            query = query.filter(FilterExecutionLog.entity_type == entity_type)
        
        # Get all logs
        logs = query.all()
        
        if not logs:
            return jsonify({
                'total_queries': 0,
                'slow_queries': 0,
                'avg_execution_time_ms': 0,
                'max_execution_time_ms': 0,
                'min_execution_time_ms': 0,
                'slow_query_percentage': 0,
                'queries_by_entity_type': {},
                'recent_slow_queries': []
            }), 200
        
        # Calculate statistics
        total_queries = len(logs)
        slow_queries = sum(1 for log in logs if log.is_slow_query)
        execution_times = [log.execution_time_ms for log in logs]
        
        avg_execution_time = sum(execution_times) / len(execution_times)
        max_execution_time = max(execution_times)
        min_execution_time = min(execution_times)
        slow_query_percentage = (slow_queries / total_queries * 100) if total_queries > 0 else 0
        
        # Queries by entity type
        queries_by_entity = {}
        for log in logs:
            if log.entity_type not in queries_by_entity:
                queries_by_entity[log.entity_type] = {
                    'total': 0,
                    'slow': 0,
                    'avg_time_ms': 0
                }
            queries_by_entity[log.entity_type]['total'] += 1
            if log.is_slow_query:
                queries_by_entity[log.entity_type]['slow'] += 1
        
        # Calculate avg time per entity type
        for entity in queries_by_entity:
            entity_logs = [log for log in logs if log.entity_type == entity]
            entity_times = [log.execution_time_ms for log in entity_logs]
            queries_by_entity[entity]['avg_time_ms'] = sum(entity_times) / len(entity_times)
        
        # Get recent slow queries (last 10)
        slow_query_logs = [log for log in logs if log.is_slow_query]
        slow_query_logs.sort(key=lambda x: x.created_at, reverse=True)
        recent_slow_queries = []
        
        for log in slow_query_logs[:10]:
            recent_slow_queries.append({
                'id': log.id,
                'entity_type': log.entity_type,
                'execution_time_ms': log.execution_time_ms,
                'result_count': log.result_count,
                'filter_config': json.loads(log.filter_config) if log.filter_config else {},
                'created_at': log.created_at.isoformat()
            })
        
        return jsonify({
            'total_queries': total_queries,
            'slow_queries': slow_queries,
            'avg_execution_time_ms': round(avg_execution_time, 2),
            'max_execution_time_ms': max_execution_time,
            'min_execution_time_ms': min_execution_time,
            'slow_query_percentage': round(slow_query_percentage, 2),
            'queries_by_entity_type': queries_by_entity,
            'recent_slow_queries': recent_slow_queries,
            'period_days': days
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
