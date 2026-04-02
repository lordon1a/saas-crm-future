"""
Sales Analytics API Routes
Provides comprehensive analytics endpoints for pipeline, deals, and performance metrics
"""
from flask import Blueprint, request, jsonify, session, send_file
from models import db
from models_crm import Deal, DealStage, Pipeline, DashboardWidget
from datetime import datetime, timedelta, UTC
from sqlalchemy import func
import logging
import json
import io

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


# Keep endpoint decorators aligned with repository convention.
login_required = login_required_api


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
        try:
            months = int(months)
        except (TypeError, ValueError):
            months = 6
        months = max(1, min(months, 36))

        now = datetime.now(UTC)
        current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Build an exact month window to avoid day-of-month rollover issues.
        total_month_index = current_month.year * 12 + (current_month.month - 1)
        start_month_index = total_month_index - (months - 1)
        start_year = start_month_index // 12
        start_month = (start_month_index % 12) + 1
        window_start = datetime(start_year, start_month, 1, tzinfo=UTC)

        # Get all won deals in the period
        deals = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.status == 'won',
            Deal.closed_at >= window_start
        ).all()

        # Group by month
        monthly_data = {}
        for deal in deals:
            if deal.closed_at:
                month_key = deal.closed_at.strftime('%Y-%m')
                if month_key not in monthly_data:
                    monthly_data[month_key] = 0.0
                monthly_data[month_key] += float(deal.value)

        # Fill in missing months with 0 using a stable month iterator.
        result = []
        for offset in range(months):
            month_index = start_month_index + offset
            year = month_index // 12
            month = (month_index % 12) + 1
            current = datetime(year, month, 1, tzinfo=UTC)
            month_key = current.strftime('%Y-%m')
            result.append({
                'month': month_key,
                'revenue': monthly_data.get(month_key, 0.0)
            })

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


# =============================================================================
# Widget CRUD Endpoints (Feature 1.3 - Customizable Dashboard Widgets)
# =============================================================================

@bp.route('/widgets', methods=['GET'])
@login_required_api
def get_widgets():
    """
    GET /api/v1/analytics/widgets
    Returns user's widget list for the current workspace.
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400
        
        widgets = DashboardWidget.query.filter(
            DashboardWidget.workspace_id == workspace_id,
            DashboardWidget.user_id == user_id
        ).order_by(DashboardWidget.pos_y, DashboardWidget.pos_x).all()
        
        return jsonify({
            'success': True,
            'widgets': [w.to_dict() for w in widgets]
        }), 200
        
    except Exception as e:
        logger.error(f'Get widgets error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to fetch widgets'}), 500


@bp.route('/widgets', methods=['POST'])
@login_required_api
def create_widget():
    """
    POST /api/v1/analytics/widgets
    Create a new dashboard widget.
    Request body: {
        widget_type: string (required),
        title: string (required),
        config_json: object (optional),
        pos_x: int (optional, default 0),
        pos_y: int (optional, default 0),
        width: int (optional, default 4),
        height: int (optional, default 3)
    }
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        widget_type = data.get('widget_type')
        title = data.get('title')
        
        if not widget_type or not title:
            return jsonify({'error': 'widget_type and title are required'}), 400
        
        # Validate widget_type
        valid_types = ['kpi_card', 'bar_chart', 'funnel', 'pie_chart', 'leaderboard', 'activity_feed', 'goal_progress', 'heatmap']
        if widget_type not in valid_types:
            return jsonify({'error': f'Invalid widget_type. Must be one of: {", ".join(valid_types)}'}), 400
        
        config_json = data.get('config_json', {})
        widget = DashboardWidget(
            workspace_id=workspace_id,
            user_id=user_id,
            widget_type=widget_type,
            title=title,
            config_json=json.dumps(config_json) if isinstance(config_json, dict) else config_json,
            pos_x=data.get('pos_x', 0),
            pos_y=data.get('pos_y', 0),
            width=data.get('width', 4),
            height=data.get('height', 3)
        )
        
        db.session.add(widget)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'widget': widget.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Create widget error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to create widget'}), 500


@bp.route('/widgets/<int:widget_id>', methods=['PATCH'])
@login_required_api
def update_widget(widget_id):
    """
    PATCH /api/v1/analytics/widgets/<id>
    Update widget configuration or position.
    Request body (all optional): {
        title: string,
        config_json: object,
        pos_x: int,
        pos_y: int,
        width: int,
        height: int
    }
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400
        
        widget = DashboardWidget.query.filter(
            DashboardWidget.id == widget_id,
            DashboardWidget.workspace_id == workspace_id,
            DashboardWidget.user_id == user_id
        ).first()
        
        if not widget:
            return jsonify({'error': 'Widget not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Update fields if provided
        if 'title' in data:
            widget.title = data['title']
        
        if 'config_json' in data:
            widget.config_json = json.dumps(data['config_json']) if isinstance(data['config_json'], dict) else data['config_json']
        
        if 'pos_x' in data:
            widget.pos_x = data['pos_x']
        
        if 'pos_y' in data:
            widget.pos_y = data['pos_y']
        
        if 'width' in data:
            widget.width = data['width']
        
        if 'height' in data:
            widget.height = data['height']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'widget': widget.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Update widget error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to update widget'}), 500


@bp.route('/widgets/<int:widget_id>', methods=['DELETE'])
@login_required_api
def delete_widget(widget_id):
    """
    DELETE /api/v1/analytics/widgets/<id>
    Delete a dashboard widget.
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400
        
        widget = DashboardWidget.query.filter(
            DashboardWidget.id == widget_id,
            DashboardWidget.workspace_id == workspace_id,
            DashboardWidget.user_id == user_id
        ).first()
        
        if not widget:
            return jsonify({'error': 'Widget not found'}), 404
        
        db.session.delete(widget)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Widget deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Delete widget error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to delete widget'}), 500


@bp.route('/widgets/reorder', methods=['POST'])
@login_required_api
def reorder_widgets():
    """
    POST /api/v1/analytics/widgets/reorder
    Bulk update widget positions after drag-and-drop.
    Request body: {
        widgets: [
            {id: int, pos_x: int, pos_y: int},
            ...
        ]
    }
    """
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400
        
        data = request.get_json()
        if not data or 'widgets' not in data:
            return jsonify({'error': 'widgets array is required'}), 400
        
        widget_updates = data['widgets']
        if not isinstance(widget_updates, list):
            return jsonify({'error': 'widgets must be an array'}), 400
        
        updated_widgets = []
        for update in widget_updates:
            if 'id' not in update:
                continue
            
            widget = DashboardWidget.query.filter(
                DashboardWidget.id == update['id'],
                DashboardWidget.workspace_id == workspace_id,
                DashboardWidget.user_id == user_id
            ).first()
            
            if widget:
                if 'pos_x' in update:
                    widget.pos_x = update['pos_x']
                if 'pos_y' in update:
                    widget.pos_y = update['pos_y']
                updated_widgets.append(widget)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'widgets': [w.to_dict() for w in updated_widgets]
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Reorder widgets error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to reorder widgets'}), 500


@bp.route('/widget-data/<int:widget_id>', methods=['GET'])
@login_required_api
def get_widget_data(widget_id):
    """
    GET /api/v1/analytics/widget-data/<id>
    Fetch data for a specific widget using AnalyticsService.
    """
    try:
        from services.analytics_service import AnalyticsService
        
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400
        
        widget = DashboardWidget.query.filter(
            DashboardWidget.id == widget_id,
            DashboardWidget.workspace_id == workspace_id,
            DashboardWidget.user_id == user_id
        ).first()
        
        if not widget:
            return jsonify({'error': 'Widget not found'}), 404
        
        # Get widget config
        config = json.loads(widget.config_json) if widget.config_json else {}
        
        # Route to appropriate AnalyticsService method based on widget_type
        widget_type = widget.widget_type
        data = {}
        
        if widget_type == 'kpi_card':
            data = AnalyticsService.get_kpi_metrics(workspace_id, config)
        elif widget_type == 'bar_chart':
            data = AnalyticsService.get_bar_chart_data(workspace_id, config)
        elif widget_type == 'funnel':
            data = AnalyticsService.get_funnel_data(workspace_id, config)
        elif widget_type == 'pie_chart':
            data = AnalyticsService.get_pie_chart_data(workspace_id, config)
        elif widget_type == 'leaderboard':
            data = AnalyticsService.get_leaderboard_data(workspace_id, config)
        elif widget_type == 'activity_feed':
            data = AnalyticsService.get_activity_feed_data(workspace_id, config)
        elif widget_type == 'goal_progress':
            data = AnalyticsService.get_goal_progress_data(workspace_id, config)
        elif widget_type == 'heatmap':
            data = AnalyticsService.get_heatmap_data(workspace_id, config)
        else:
            return jsonify({'error': f'Unknown widget type: {widget_type}'}), 400
        
        return jsonify({
            'success': True,
            'widget_id': widget_id,
            'widget_type': widget_type,
            'data': data
        }), 200
        
    except Exception as e:
        logger.error(f'Get widget data error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to fetch widget data'}), 500


# =============================================================================
# Saved Reports & Scheduling Endpoints
# =============================================================================

@bp.route('/reports', methods=['GET'])
@login_required
def list_saved_reports():
    """List saved reports for current workspace."""
    try:
        from services.report_service import ReportService

        workspace_id = session.get('workspace_id')
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400

        reports = ReportService.list_reports(workspace_id)
        return jsonify({'success': True, 'reports': reports}), 200

    except Exception as e:
        logger.error(f'List reports error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to fetch reports'}), 500


@bp.route('/reports', methods=['POST'])
@login_required
def create_saved_report():
    """Create a saved report definition."""
    try:
        from services.report_service import ReportService

        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400

        data = request.get_json(silent=True) or {}
        report = ReportService.create_report(
            workspace_id=workspace_id,
            created_by=user_id,
            name=data.get('name'),
            report_type=data.get('report_type'),
            config=data.get('config') or {}
        )

        return jsonify({
            'success': True,
            'report': ReportService.serialize_report(report)
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Create report error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to create report'}), 500


@bp.route('/reports/custom-query', methods=['POST'])
@login_required
def run_custom_report_preview():
    """Preview a custom report query without saving a report."""
    try:
        from services.report_service import ReportService

        workspace_id = session.get('workspace_id')
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400

        data = request.get_json(silent=True) or {}
        result = ReportService.run_custom_report(workspace_id, {
            'dimension': data.get('dimension'),
            'metric': data.get('metric'),
        })

        return jsonify({
            'success': True,
            'report_type': 'custom',
            'generated_at': datetime.now(UTC).isoformat(),
            'data': result,
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Custom report preview error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to run custom report'}), 500


@bp.route('/reports/<int:report_id>/run', methods=['GET'])
@login_required
def run_saved_report(report_id):
    """Execute a saved report and return the output."""
    try:
        from services.report_service import ReportService

        workspace_id = session.get('workspace_id')
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400

        report = ReportService.get_report(report_id, workspace_id)
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        result = ReportService.run_report(report, workspace_id)
        return jsonify({
            'success': True,
            'report': ReportService.serialize_report(report),
            **result,
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Run report error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to run report'}), 500


@bp.route('/reports/<int:report_id>/export', methods=['GET'])
@login_required
def export_saved_report(report_id):
    """Export a saved report output as Excel or PDF."""
    try:
        from services.report_service import ReportService

        workspace_id = session.get('workspace_id')
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400

        export_format = (request.args.get('format', 'excel') or 'excel').lower()
        if export_format not in {'excel', 'pdf'}:
            return jsonify({'error': 'Invalid export format'}), 400

        report = ReportService.get_report(report_id, workspace_id)
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        report_result = ReportService.run_report(report, workspace_id)

        if export_format == 'pdf':
            payload = ReportService.export_pdf(report.name, report_result)
            mimetype = 'application/pdf'
            extension = 'pdf'
        else:
            payload = ReportService.export_excel(report.name, report_result)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            extension = 'xlsx'

        base_name = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in (report.name or 'report'))
        safe_name = base_name.strip('_') or 'report'

        return send_file(
            io.BytesIO(payload),
            as_attachment=True,
            download_name=f'{safe_name}.{extension}',
            mimetype=mimetype,
        )

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Export report error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to export report'}), 500


@bp.route('/report-schedules', methods=['POST'])
@login_required
def create_report_schedule():
    """Create a report delivery schedule."""
    try:
        from services.report_service import ReportService

        workspace_id = session.get('workspace_id')
        if not workspace_id or not isinstance(workspace_id, int):
            return jsonify({'error': 'Invalid workspace'}), 400

        data = request.get_json(silent=True) or {}
        schedule = ReportService.create_schedule(
            workspace_id=workspace_id,
            report_id=data.get('report_id'),
            frequency=data.get('frequency'),
            delivery_channel=(data.get('delivery_channel') or 'email'),
            delivery_target=data.get('delivery_target'),
        )

        return jsonify({
            'success': True,
            'schedule': {
                'id': schedule.id,
                'report_id': schedule.report_id,
                'frequency': schedule.frequency,
                'delivery_channel': schedule.delivery_channel,
                'delivery_target': schedule.delivery_target,
                'is_active': schedule.is_active,
                'created_at': schedule.created_at.isoformat() if schedule.created_at else None,
            },
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Create report schedule error: {e}', exc_info=True)
        return jsonify({'error': 'Failed to create report schedule'}), 500

