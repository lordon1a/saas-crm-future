"""
Analytics Routes
API endpoints for advanced reporting and analytics
"""
import io
import time

from flask import Blueprint, request, jsonify, session, send_file
from services.analytics_service import AnalyticsService
from services.report_service import ReportService
from functools import wraps
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')
_DASHBOARD_CACHE = {}
_DASHBOARD_CACHE_TTL_SECONDS = 30


def login_required(f):
    """Decorator to require login for API endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        if not session.get('workspace_id'):
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated


@bp.route('/kpis', methods=['GET'])
@login_required
def get_kpis():
    """
    Get critical KPI metrics
    
    Returns:
        JSON: {
            'total_revenue': float,
            'open_opportunities': int,
            'total_contacts': int,
            'total_companies': int,
            'active_tasks': int,
            'completed_tasks_this_month': int
        }
    """
    try:
        workspace_id = session.get('workspace_id')
        kpis = AnalyticsService.get_kpi_metrics(workspace_id)
        return jsonify(kpis), 200
        
    except Exception as e:
        logger.error(f'Failed to get KPIs: {e}')
        return jsonify({'error': 'Failed to fetch KPI metrics'}), 500


@bp.route('/pipeline-distribution', methods=['GET'])
@login_required
def get_pipeline_distribution():
    """
    Get deal distribution across pipeline stages
    
    Returns:
        JSON: {
            'stages': [
                {
                    'stage_name': str,
                    'deal_count': int,
                    'total_value': float,
                    'probability': float,
                    'weighted_value': float
                }
            ]
        }
    """
    try:
        workspace_id = session.get('workspace_id')
        distribution = AnalyticsService.get_pipeline_distribution(workspace_id)
        return jsonify(distribution), 200
        
    except Exception as e:
        logger.error(f'Failed to get pipeline distribution: {e}')
        return jsonify({'error': 'Failed to fetch pipeline distribution'}), 500


@bp.route('/win-loss-ratio', methods=['GET'])
@login_required
def get_win_loss_ratio():
    """
    Get win/loss ratio for closed deals
    
    Returns:
        JSON: {
            'won_count': int,
            'lost_count': int,
            'won_value': float,
            'lost_value': float,
            'win_rate': float,
            'total_closed': int
        }
    """
    try:
        workspace_id = session.get('workspace_id')
        ratio = AnalyticsService.get_win_loss_ratio(workspace_id)
        return jsonify(ratio), 200
        
    except Exception as e:
        logger.error(f'Failed to get win/loss ratio: {e}')
        return jsonify({'error': 'Failed to fetch win/loss ratio'}), 500


@bp.route('/revenue-trend', methods=['GET'])
@login_required
def get_revenue_trend():
    """
    Get revenue trend over time
    
    Query params:
        days: Number of days to look back (default: 30)
    
    Returns:
        JSON: {
            'dates': [str],
            'revenue': [float]
        }
    """
    try:
        workspace_id = session.get('workspace_id')
        days = int(request.args.get('days', 30))
        
        if days < 1 or days > 365:
            return jsonify({'error': 'Days must be between 1 and 365'}), 400
        
        trend = AnalyticsService.get_revenue_trend(workspace_id, days)
        return jsonify(trend), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid days parameter'}), 400
    except Exception as e:
        logger.error(f'Failed to get revenue trend: {e}')
        return jsonify({'error': 'Failed to fetch revenue trend'}), 500


@bp.route('/top-performers', methods=['GET'])
@login_required
def get_top_performers():
    """
    Get top performing users by deal value
    
    Query params:
        limit: Number of top performers to return (default: 5)
    
    Returns:
        JSON: {
            'performers': [
                {
                    'user_name': str,
                    'deals_won': int,
                    'total_value': float
                }
            ]
        }
    """
    try:
        workspace_id = session.get('workspace_id')
        limit = int(request.args.get('limit', 5))
        
        if limit < 1 or limit > 20:
            return jsonify({'error': 'Limit must be between 1 and 20'}), 400
        
        performers = AnalyticsService.get_top_performers(workspace_id, limit)
        return jsonify(performers), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid limit parameter'}), 400
    except Exception as e:
        logger.error(f'Failed to get top performers: {e}')
        return jsonify({'error': 'Failed to fetch top performers'}), 500


@bp.route('/task-completion', methods=['GET'])
@login_required
def get_task_completion():
    """
    Get task completion statistics
    
    Returns:
        JSON: {
            'total_tasks': int,
            'completed_tasks': int,
            'completion_rate': float,
            'overdue_tasks': int
        }
    """
    try:
        workspace_id = session.get('workspace_id')
        stats = AnalyticsService.get_task_completion_rate(workspace_id)
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f'Failed to get task completion stats: {e}')
        return jsonify({'error': 'Failed to fetch task completion stats'}), 500


@bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard_data():
    """
    Get all dashboard data in one request (optimized)
    
    Returns:
        JSON: {
            'kpis': {...},
            'pipeline_distribution': {...},
            'win_loss_ratio': {...},
            'task_completion': {...}
        }
    """
    try:
        workspace_id = session.get('workspace_id')

        cache_key = f'dashboard:{workspace_id}'
        now = time.time()
        cached = _DASHBOARD_CACHE.get(cache_key)
        if cached and (now - cached['ts']) <= _DASHBOARD_CACHE_TTL_SECONDS:
            return jsonify(cached['payload']), 200
        
        # Fetch all data
        dashboard_data = {
            'kpis': AnalyticsService.get_kpi_metrics(workspace_id),
            'pipeline_distribution': AnalyticsService.get_pipeline_distribution(workspace_id),
            'win_loss_ratio': AnalyticsService.get_win_loss_ratio(workspace_id),
            'task_completion': AnalyticsService.get_task_completion_rate(workspace_id)
        }

        _DASHBOARD_CACHE[cache_key] = {
            'ts': now,
            'payload': dashboard_data,
        }
        
        return jsonify(dashboard_data), 200
        
    except Exception as e:
        logger.error(f'Failed to get dashboard data: {e}')
        return jsonify({'error': 'Failed to fetch dashboard data'}), 500


@bp.route('/reports', methods=['GET'])
@login_required
def list_reports():
    """List saved reports and report schedules."""
    try:
        workspace_id = session.get('workspace_id')
        return jsonify({
            'reports': ReportService.list_reports(workspace_id),
            'schedules': ReportService.list_schedules(workspace_id),
        }), 200
    except Exception as e:
        logger.error(f'Failed to list reports: {e}')
        return jsonify({'error': 'Failed to list reports'}), 500


@bp.route('/reports', methods=['POST'])
@login_required
def create_report():
    """Create a saved report definition."""
    try:
        data = request.get_json() or {}
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')

        report = ReportService.create_report(
            workspace_id=workspace_id,
            created_by=user_id,
            name=data.get('name'),
            report_type=data.get('report_type'),
            config=data.get('config') or {},
        )
        return jsonify({'report': ReportService.serialize_report(report)}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Failed to create report: {e}')
        return jsonify({'error': 'Failed to create report'}), 500


@bp.route('/reports/custom-query', methods=['POST'])
@login_required
def run_custom_query():
    """Run custom report builder query preview."""
    try:
        workspace_id = session.get('workspace_id')
        data = request.get_json() or {}
        result = ReportService.run_custom_report(workspace_id, data)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Failed to run custom report: {e}')
        return jsonify({'error': 'Failed to run custom report'}), 500


@bp.route('/reports/<int:report_id>/run', methods=['GET'])
@login_required
def run_saved_report(report_id):
    """Run a saved report and return output."""
    try:
        workspace_id = session.get('workspace_id')
        report = ReportService.get_report(report_id, workspace_id)
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        output = ReportService.run_report(report, workspace_id)
        return jsonify(output), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Failed to run report {report_id}: {e}')
        return jsonify({'error': 'Failed to run report'}), 500


@bp.route('/reports/<int:report_id>/export', methods=['GET'])
@login_required
def export_report(report_id):
    """Export a saved report as Excel or PDF."""
    try:
        workspace_id = session.get('workspace_id')
        export_format = (request.args.get('format', 'excel') or 'excel').lower()

        report = ReportService.get_report(report_id, workspace_id)
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        output = ReportService.run_report(report, workspace_id)

        if export_format == 'pdf':
            payload = ReportService.export_pdf(report.name, output)
            return send_file(
                io.BytesIO(payload),
                as_attachment=True,
                download_name=f'report_{report.id}.pdf',
                mimetype='application/pdf',
            )

        payload = ReportService.export_excel(report.name, output)
        return send_file(
            io.BytesIO(payload),
            as_attachment=True,
            download_name=f'report_{report.id}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Failed to export report {report_id}: {e}')
        return jsonify({'error': 'Failed to export report'}), 500


@bp.route('/report-schedules', methods=['POST'])
@login_required
def create_report_schedule():
    """Create report schedule metadata."""
    try:
        workspace_id = session.get('workspace_id')
        data = request.get_json() or {}

        schedule = ReportService.create_schedule(
            workspace_id=workspace_id,
            report_id=data.get('report_id'),
            frequency=data.get('frequency'),
            delivery_channel=data.get('delivery_channel', 'email'),
            delivery_target=data.get('delivery_target'),
        )
        return jsonify({'schedule': {
            'id': schedule.id,
            'report_id': schedule.report_id,
            'frequency': schedule.frequency,
            'delivery_channel': schedule.delivery_channel,
            'delivery_target': schedule.delivery_target,
            'is_active': schedule.is_active,
        }}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Failed to create report schedule: {e}')
        return jsonify({'error': 'Failed to create report schedule'}), 500
