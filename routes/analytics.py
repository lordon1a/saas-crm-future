"""
Sales Analytics API Routes
Provides comprehensive analytics endpoints for pipeline, deals, and performance metrics
"""
from flask import Blueprint, request, jsonify, session
from models import db
from models_crm import Deal, DealStage, Pipeline
from datetime import datetime, timedelta, UTC
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('analytics', __name__, url_prefix='/api/v1/analytics')


def login_required_api(f):
    """API authentication decorator with workspace validation"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400
            
        return f(*args, **kwargs)
    return decorated


@bp.route('/overview', methods=['GET'])
@login_required_api
def get_analytics_overview():
    """
    Comprehensive analytics overview endpoint
    Returns: Funnel data, conversion rate, monthly performance, win/loss ratio
    """
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400
        
        # Get funnel data (active deals by stage)
        funnel_data = _get_funnel_data(workspace_id)
        
        # Get conversion rate
        conversion_rate = _get_conversion_rate(workspace_id)
        
        # Get monthly performance (last 6 months)
        monthly_performance = _get_monthly_performance(workspace_id, months=6)
        
        # Get win/loss ratio
        win_loss_ratio = _get_win_loss_ratio(workspace_id)
        
        # Get average sales cycle
        avg_sales_cycle = _get_average_sales_cycle(workspace_id)
        
        return jsonify({
            'success': True,
            'data': {
                'funnel': funnel_data,
                'conversion_rate': conversion_rate,
                'monthly_performance': monthly_performance,
                'win_loss_ratio': win_loss_ratio,
                'avg_sales_cycle_days': avg_sales_cycle
            }
        }), 200
        
    except Exception as e:
        logger.error(f'Analytics overview error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to fetch analytics data'}), 500


def _get_funnel_data(workspace_id):
    """
    Get sales funnel data: active deals count and total value per stage
    """
    try:
        results = db.session.query(
            DealStage.name,
            DealStage.order,
            func.count(Deal.id).label('deal_count'),
            func.coalesce(func.sum(Deal.value), 0).label('total_value')
        ).join(
            Deal, Deal.stage_id == DealStage.id
        ).filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.status == 'open'
        ).group_by(
            DealStage.id,
            DealStage.name,
            DealStage.order
        ).order_by(
            DealStage.order
        ).all()
        
        stages = []
        for stage_name, order, deal_count, total_value in results:
            stages.append({
                'stage_name': stage_name,
                'order': order,
                'deal_count': deal_count,
                'total_value': float(total_value)
            })
        
        return {'stages': stages}
        
    except Exception as e:
        logger.error(f'Funnel data error: {e}')
        return {'stages': []}


def _get_conversion_rate(workspace_id):
    """
    Calculate conversion rate: (Won Deals / Total Closed Deals) * 100
    """
    try:
        won_count = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.status == 'won'
        ).count()
        
        total_closed = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.status.in_(['won', 'lost'])
        ).count()
        
        if total_closed == 0:
            return {
                'won_count': 0,
                'total_closed': 0,
                'rate': 0.0
            }
        
        rate = (won_count / total_closed) * 100
        
        return {
            'won_count': won_count,
            'total_closed': total_closed,
            'rate': round(rate, 2)
        }
        
    except Exception as e:
        logger.error(f'Conversion rate error: {e}')
        return {'won_count': 0, 'total_closed': 0, 'rate': 0.0}


def _get_monthly_performance(workspace_id, months=6):
    """
    Get monthly won deal totals for the last N months
    """
    try:
        now = datetime.now(UTC)
        start_date = now - timedelta(days=months * 30)
        
        # Get all won deals in the period
        deals = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.status == 'won',
            Deal.closed_at >= start_date
        ).all()
        
        # Group by month
        monthly_data = {}
        for deal in deals:
            if deal.closed_at:
                month_key = deal.closed_at.strftime('%Y-%m')
                if month_key not in monthly_data:
                    monthly_data[month_key] = 0.0
                monthly_data[month_key] += float(deal.value)
        
        # Fill in missing months with 0
        result = []
        current = start_date
        while current <= now:
            month_key = current.strftime('%Y-%m')
            result.append({
                'month': month_key,
                'revenue': monthly_data.get(month_key, 0.0)
            })
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        return {'months': result}
        
    except Exception as e:
        logger.error(f'Monthly performance error: {e}')
        return {'months': []}


def _get_win_loss_ratio(workspace_id):
    """
    Get win/loss ratio for closed deals
    """
    try:
        won_count = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.status == 'won'
        ).count()
        
        lost_count = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.status == 'lost'
        ).count()
        
        return {
            'won': won_count,
            'lost': lost_count
        }
        
    except Exception as e:
        logger.error(f'Win/loss ratio error: {e}')
        return {'won': 0, 'lost': 0}


def _get_average_sales_cycle(workspace_id):
    """
    Calculate average sales cycle duration in days for won deals
    """
    try:
        # Get won deals from last 90 days
        ninety_days_ago = datetime.now(UTC) - timedelta(days=90)
        
        deals = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.status == 'won',
            Deal.closed_at.isnot(None),
            Deal.closed_at >= ninety_days_ago
        ).all()
        
        if not deals:
            return 0
        
        total_days = 0
        count = 0
        
        for deal in deals:
            if deal.closed_at and deal.created_at:
                duration = (deal.closed_at - deal.created_at).days
                if duration >= 0:
                    total_days += duration
                    count += 1
        
        if count == 0:
            return 0
        
        return round(total_days / count, 1)
        
    except Exception as e:
        logger.error(f'Average sales cycle error: {e}')
        return 0


@bp.route('/dashboard', methods=['GET'])
@login_required_api
def get_dashboard_data():
    """
    Dashboard endpoint combining all analytics data
    Used by analytics_dashboard.html
    """
    try:
        from services.analytics_service import AnalyticsService
        
        workspace_id = session.get('workspace_id')
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400
        
        # Get KPIs
        kpis = AnalyticsService.get_kpi_metrics(workspace_id)
        
        # Get pipeline distribution
        pipeline_distribution = AnalyticsService.get_pipeline_distribution(workspace_id)
        
        # Get win/loss ratio
        win_loss_ratio = AnalyticsService.get_win_loss_ratio(workspace_id)
        
        # Get task completion
        task_completion = AnalyticsService.get_task_completion_rate(workspace_id)
        
        return jsonify({
            'success': True,
            'kpis': kpis,
            'pipeline_distribution': pipeline_distribution,
            'win_loss_ratio': win_loss_ratio,
            'task_completion': task_completion
        }), 200
        
    except Exception as e:
        logger.error(f'Dashboard data error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to fetch dashboard data'}), 500

