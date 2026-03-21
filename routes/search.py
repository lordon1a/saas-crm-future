"""
Search Logging API Routes
Endpoints for tracking and analyzing search behavior
"""
from flask import Blueprint, request, jsonify, session
from datetime import datetime
from functools import wraps
import logging

logger = logging.getLogger(__name__)

search_bp = Blueprint('search', __name__)


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


from services.search_log_service import SearchLogService


@search_bp.route('/api/v1/search/log', methods=['POST'])
@login_required
def log_search():
    """
    Log a search query
    
    Body:
    {
        "search_query": "john doe",
        "search_type": "contact",
        "entity_type": "contact",
        "results_count": 5,
        "search_duration_ms": 120,
        "filters_applied": "{...}"
    }
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        
        if not data or not data.get('search_query'):
            return jsonify({'error': 'search_query is required'}), 400
        
        # Get user agent and IP
        user_agent = request.headers.get('User-Agent')
        ip_address = request.remote_addr
        
        log = SearchLogService.log_search(
            workspace_id=workspace_id,
            user_id=user_id,
            search_query=data['search_query'],
            search_type=data.get('search_type', 'global'),
            results_count=data.get('results_count', 0),
            entity_type=data.get('entity_type'),
            search_duration_ms=data.get('search_duration_ms'),
            filters_applied=data.get('filters_applied'),
            user_agent=user_agent,
            ip_address=ip_address
        )
        
        if log:
            return jsonify({
                'success': True,
                'log_id': log.id
            }), 201
        else:
            return jsonify({'error': 'Failed to log search'}), 500
        
    except Exception as e:
        logger.error(f"Error logging search: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@search_bp.route('/api/v1/search/log/<int:log_id>/click', methods=['POST'])
@login_required
def log_click(log_id):
    """
    Log a click on search result
    
    Body:
    {
        "result_id": 123,
        "result_type": "contact"
    }
    """
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        
        if not data or not data.get('result_id') or not data.get('result_type'):
            return jsonify({'error': 'result_id and result_type are required'}), 400
        
        success = SearchLogService.log_click(
            log_id=log_id,
            result_id=data['result_id'],
            result_type=data['result_type']
        )
        
        if success:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Log not found'}), 404
        
    except Exception as e:
        logger.error(f"Error logging click: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@search_bp.route('/api/v1/search/history', methods=['GET'])
@login_required
def get_search_history():
    """
    Get user's search history
    
    Query params:
    - limit: Number of results (default: 20, max: 100)
    - entity_type: Filter by entity type (optional)
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        limit = min(request.args.get('limit', 20, type=int), 100)
        entity_type = request.args.get('entity_type')
        
        history = SearchLogService.get_user_history(
            workspace_id=workspace_id,
            user_id=user_id,
            limit=limit,
            entity_type=entity_type
        )
        
        return jsonify({
            'history': history,
            'count': len(history)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting search history: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@search_bp.route('/api/v1/search/popular', methods=['GET'])
@login_required
def get_popular_searches():
    """
    Get popular search queries
    
    Query params:
    - days: Number of days to look back (default: 7)
    - limit: Number of results (default: 10, max: 50)
    - search_type: Filter by search type (optional)
    """
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        days = request.args.get('days', 7, type=int)
        limit = min(request.args.get('limit', 10, type=int), 50)
        search_type = request.args.get('search_type')
        
        popular = SearchLogService.get_popular_searches(
            workspace_id=workspace_id,
            days=days,
            limit=limit,
            search_type=search_type
        )
        
        return jsonify({
            'popular_searches': popular,
            'count': len(popular),
            'days': days
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting popular searches: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@search_bp.route('/api/v1/search/analytics', methods=['GET'])
@login_required
def get_search_analytics():
    """
    Get search analytics for workspace
    
    Query params:
    - start_date: Start date (ISO format, optional)
    - end_date: End date (ISO format, optional)
    """
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Parse dates
        start_date = None
        end_date = None
        
        if request.args.get('start_date'):
            try:
                start_date = datetime.fromisoformat(request.args.get('start_date'))
            except ValueError:
                return jsonify({'error': 'Invalid start_date format'}), 400
        
        if request.args.get('end_date'):
            try:
                end_date = datetime.fromisoformat(request.args.get('end_date'))
            except ValueError:
                return jsonify({'error': 'Invalid end_date format'}), 400
        
        analytics = SearchLogService.get_analytics(
            workspace_id=workspace_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify(analytics), 200
        
    except Exception as e:
        logger.error(f"Error getting search analytics: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500
