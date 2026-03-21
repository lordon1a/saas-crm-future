"""
Calendar Routes
API endpoints for calendar view and task scheduling
"""
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from functools import wraps
from services.task_service import TaskService
from models_crm import db, Contact, Company, Deal, Task
from models import User
from sqlalchemy import or_
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

calendar_bp = Blueprint('calendar', __name__)


def login_required(f):
    """Session-based login required decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@calendar_bp.route('/calendar')
@login_required
def calendar_page():
    """Render calendar page"""
    return render_template('calendar.html')


@calendar_bp.route('/api/v1/calendar/events', methods=['GET'])
@login_required
def get_calendar_events():
    """
    Takvim görünümü için görevleri getir.
    
    Query Parameters:
        - start: Başlangıç tarihi (ISO format, required)
        - end: Bitiş tarihi (ISO format, required)
        - task_type: Görev tipi filtresi (opsiyonel: call, meeting, email, todo, follow_up, other)
        - assignee_id: Atanan kişi filtresi (opsiyonel, 'me' veya user_id)
        - status: Durum filtresi (opsiyonel: pending, completed, cancelled, overdue)
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        
        if not start_str or not end_str:
            return jsonify({'error': 'start and end parameters required'}), 400
        
        try:
            start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}), 400
        
        filters = {}
        if request.args.get('task_type'):
            filters['task_type'] = request.args.get('task_type')
        if request.args.get('assignee_id'):
            filters['assignee_id'] = request.args.get('assignee_id')
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
        
        events = TaskService.get_tasks_for_calendar(
            workspace_id=workspace_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            filters=filters
        )
        
        # Enrich events with contact/company/deal names
        for ev in events:
            props = ev.get('extendedProps', {})
            if props.get('contact_id'):
                contact = Contact.query.get(props['contact_id'])
                props['contact_name'] = contact.full_name if contact else None
            if props.get('company_id'):
                company = Company.query.get(props['company_id'])
                props['company_name'] = company.name if company else None
            if props.get('deal_id'):
                deal = Deal.query.get(props['deal_id'])
                props['deal_name'] = deal.name if deal else None
        
        return jsonify({'events': events}), 200
        
    except Exception as e:
        logger.error(f"Calendar events error: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@calendar_bp.route('/api/v1/calendar/upcoming', methods=['GET'])
@login_required
def upcoming_events():
    """Get upcoming events from now"""
    try:
        workspace_id = session.get('workspace_id')
        limit = request.args.get('limit', 8, type=int)
        now = datetime.utcnow()
        
        tasks = Task.query.filter(
            Task.workspace_id == workspace_id,
            Task.start_time >= now,
            Task.status.notin_(['completed', 'cancelled'])
        ).order_by(Task.start_time.asc()).limit(limit).all()
        
        return jsonify({'events': [t.to_calendar_event() for t in tasks]})
    except Exception as e:
        logger.error(f"Upcoming events error: {str(e)}", exc_info=True)
        return jsonify({'events': []})


@calendar_bp.route('/api/v1/calendar/contacts-search', methods=['GET'])
@login_required
def search_contacts_for_calendar():
    """Search contacts for calendar event linking"""
    workspace_id = session.get('workspace_id')
    q = request.args.get('q', '').strip()
    query = Contact.query.filter_by(workspace_id=workspace_id, is_deleted=False)
    if q:
        query = query.filter(or_(Contact.first_name.ilike(f'%{q}%'), Contact.last_name.ilike(f'%{q}%')))
    contacts = query.limit(20).all()
    return jsonify({'contacts': [{'id': c.id, 'name': c.full_name} for c in contacts]})


@calendar_bp.route('/api/v1/calendar/companies-search', methods=['GET'])
@login_required
def search_companies_for_calendar():
    """Search companies for calendar event linking"""
    workspace_id = session.get('workspace_id')
    q = request.args.get('q', '').strip()
    query = Company.query.filter_by(workspace_id=workspace_id, is_deleted=False)
    if q:
        query = query.filter(Company.name.ilike(f'%{q}%'))
    companies = query.limit(20).all()
    return jsonify({'companies': [{'id': c.id, 'name': c.name} for c in companies]})


@calendar_bp.route('/api/v1/calendar/deals-search', methods=['GET'])
@login_required
def search_deals_for_calendar():
    """Search deals for calendar event linking"""
    workspace_id = session.get('workspace_id')
    q = request.args.get('q', '').strip()
    query = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False)
    if q:
        query = query.filter(Deal.name.ilike(f'%{q}%'))
    deals = query.limit(20).all()
    return jsonify({'deals': [{'id': d.id, 'name': d.name} for d in deals]})


@calendar_bp.route('/api/v1/calendar/team', methods=['GET'])
@login_required
def get_team_for_calendar():
    """Get team members for assignee selection"""
    workspace_id = session.get('workspace_id')
    users = User.query.filter_by(workspace_id=workspace_id).with_entities(
        User.id, User.name, User.email
    ).all()
    return jsonify({'users': [{'id': u.id, 'name': u.name or u.email} for u in users]})
