"""
Super Admin Routes
Platform-level administration endpoints for managing tenants and analytics
"""
from flask import Blueprint, request, jsonify, session
from models import db, Workspace, User, Customer, Conversation, Message, SuperAdmin, ImpersonateLog
from functools import wraps
from datetime import datetime, timedelta
import jwt
import os
import logging
from werkzeug.security import check_password_hash
from sqlalchemy import func, text

logger = logging.getLogger(__name__)

bp = Blueprint('super_admin', __name__, url_prefix='/api/super')

# JWT secret from environment
JWT_SECRET = os.environ.get('JWT_SECRET', os.environ.get('SECRET_KEY', 'dev-secret-key'))

def jwt_required(f):
    """Decorator to require JWT authentication for super admin endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            super_admin_id = payload.get('super_admin_id')
            
            if not super_admin_id:
                return jsonify({'error': 'Invalid token'}), 401
            
            # Verify super admin exists and is active
            super_admin = SuperAdmin.query.get(super_admin_id)
            if not super_admin or not super_admin.is_active:
                return jsonify({'error': 'Super admin not found or inactive'}), 401
            
            # Attach to request context
            request.super_admin = super_admin
            
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    
    return decorated


# ═══ AUTHENTICATION ═══

@bp.route('/auth/login', methods=['POST'])
def login():
    """Super admin login - returns JWT token"""
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400
    
    try:
        super_admin = SuperAdmin.query.filter_by(email=data['email']).first()
        
        if not super_admin or not super_admin.is_active:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not check_password_hash(super_admin.password_hash, data['password']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Update last login
        super_admin.last_login = datetime.utcnow()
        db.session.commit()
        
        # Generate JWT token (24 hour expiry)
        token = jwt.encode({
            'super_admin_id': super_admin.id,
            'email': super_admin.email,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, JWT_SECRET, algorithm='HS256')
        
        logger.info(f"Super admin login: {super_admin.email}")
        
        return jsonify({
            'token': token,
            'super_admin': {
                'id': super_admin.id,
                'email': super_admin.email,
                'name': super_admin.name
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Super admin login error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


# ═══ TENANT MANAGEMENT ═══

@bp.route('/tenants', methods=['GET'])
@jwt_required
def get_tenants():
    """Get all workspaces with statistics"""
    try:
        workspaces = Workspace.query.all()
        
        result = []
        for workspace in workspaces:
            # Get statistics
            user_count = User.query.filter_by(workspace_id=workspace.id).count()
            customer_count = Customer.query.filter_by(workspace_id=workspace.id).count()
            conversation_count = Conversation.query.filter_by(workspace_id=workspace.id).count()
            
            # Get message count (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            message_count = Message.query.join(Conversation).filter(
                Conversation.workspace_id == workspace.id,
                Message.timestamp >= thirty_days_ago
            ).count()
            
            result.append({
                'id': workspace.id,
                'company_name': workspace.company_name,
                'created_at': workspace.created_at.isoformat(),
                'whatsapp_connected': bool(workspace.whatsapp_phone_number_id),
                'telegram_connected': bool(workspace.telegram_bot_token),
                'stats': {
                    'users': user_count,
                    'customers': customer_count,
                    'conversations': conversation_count,
                    'messages_30d': message_count
                }
            })
        
        return jsonify({
            'tenants': result,
            'total': len(result)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting tenants: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/tenants/<int:workspace_id>', methods=['GET'])
@jwt_required
def get_tenant(workspace_id):
    """Get single tenant details"""
    try:
        workspace = Workspace.query.get(workspace_id)
        
        if not workspace:
            return jsonify({'error': 'Tenant not found'}), 404
        
        # Get detailed statistics
        users = User.query.filter_by(workspace_id=workspace_id).all()
        customer_count = Customer.query.filter_by(workspace_id=workspace_id).count()
        conversation_count = Conversation.query.filter_by(workspace_id=workspace_id).count()
        
        # Message stats by day (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        daily_messages = db.session.query(
            func.date(Message.timestamp).label('date'),
            func.count(Message.id).label('count')
        ).join(Conversation).filter(
            Conversation.workspace_id == workspace_id,
            Message.timestamp >= seven_days_ago
        ).group_by(func.date(Message.timestamp)).all()
        
        return jsonify({
            'id': workspace.id,
            'company_name': workspace.company_name,
            'created_at': workspace.created_at.isoformat(),
            'whatsapp_phone_number_id': workspace.whatsapp_phone_number_id,
            'waba_id': workspace.waba_id,
            'telegram_bot_token': bool(workspace.telegram_bot_token),
            'users': [{
                'id': u.id,
                'name': u.name,
                'email': u.email,
                'role': u.role
            } for u in users],
            'stats': {
                'customers': customer_count,
                'conversations': conversation_count,
                'daily_messages': [{
                    'date': str(dm.date),
                    'count': dm.count
                } for dm in daily_messages]
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting tenant {workspace_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/tenants/<int:workspace_id>/suspend', methods=['POST'])
@jwt_required
def suspend_tenant(workspace_id):
    """Suspend a tenant (placeholder - implement suspension logic)"""
    try:
        workspace = Workspace.query.get(workspace_id)
        
        if not workspace:
            return jsonify({'error': 'Tenant not found'}), 404
        
        # TODO: Add is_suspended column to Workspace model
        # workspace.is_suspended = True
        # db.session.commit()
        
        logger.warning(f"Tenant suspension requested for workspace {workspace_id} by super admin {request.super_admin.email}")
        
        return jsonify({
            'message': 'Tenant suspension feature not yet implemented',
            'workspace_id': workspace_id
        }), 501
        
    except Exception as e:
        logger.error(f"Error suspending tenant {workspace_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/tenants/<int:workspace_id>/activate', methods=['POST'])
@jwt_required
def activate_tenant(workspace_id):
    """Activate a suspended tenant"""
    try:
        workspace = Workspace.query.get(workspace_id)
        
        if not workspace:
            return jsonify({'error': 'Tenant not found'}), 404
        
        # TODO: Add is_suspended column to Workspace model
        # workspace.is_suspended = False
        # db.session.commit()
        
        logger.info(f"Tenant activation requested for workspace {workspace_id} by super admin {request.super_admin.email}")
        
        return jsonify({
            'message': 'Tenant activation feature not yet implemented',
            'workspace_id': workspace_id
        }), 501
        
    except Exception as e:
        logger.error(f"Error activating tenant {workspace_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/tenants/<int:workspace_id>/plan', methods=['PATCH'])
@jwt_required
def update_tenant_plan(workspace_id):
    """Update tenant plan (free/starter/pro)"""
    data = request.get_json()
    
    if not data or not data.get('plan'):
        return jsonify({'error': 'Plan required'}), 400
    
    plan = data['plan']
    if plan not in ['free', 'starter', 'pro']:
        return jsonify({'error': 'Invalid plan. Must be: free, starter, or pro'}), 400
    
    try:
        workspace = Workspace.query.get(workspace_id)
        
        if not workspace:
            return jsonify({'error': 'Tenant not found'}), 404
        
        # TODO: Add plan column to Workspace model
        # workspace.plan = plan
        # db.session.commit()
        
        logger.info(f"Plan update requested for workspace {workspace_id} to {plan} by super admin {request.super_admin.email}")
        
        return jsonify({
            'message': 'Plan update feature not yet implemented',
            'workspace_id': workspace_id,
            'requested_plan': plan
        }), 501
        
    except Exception as e:
        logger.error(f"Error updating plan for tenant {workspace_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


# ═══ ANALYTICS ═══

@bp.route('/analytics/overview', methods=['GET'])
@jwt_required
def get_analytics_overview():
    """Platform-wide analytics: DAU, MAU, message counts"""
    try:
        # Total counts
        total_workspaces = Workspace.query.count()
        total_users = User.query.count()
        total_customers = Customer.query.count()
        
        # DAU (Daily Active Users) - users who sent messages today
        today = datetime.utcnow().date()
        dau = db.session.query(func.count(func.distinct(Message.user_id))).join(Conversation).filter(
            func.date(Message.timestamp) == today
        ).scalar() or 0
        
        # MAU (Monthly Active Users) - users who sent messages in last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        mau = db.session.query(func.count(func.distinct(Message.user_id))).join(Conversation).filter(
            Message.timestamp >= thirty_days_ago
        ).scalar() or 0
        
        # Message counts
        messages_today = Message.query.join(Conversation).filter(
            func.date(Message.timestamp) == today
        ).count()
        
        messages_30d = Message.query.join(Conversation).filter(
            Message.timestamp >= thirty_days_ago
        ).count()
        
        return jsonify({
            'platform': {
                'total_workspaces': total_workspaces,
                'total_users': total_users,
                'total_customers': total_customers
            },
            'activity': {
                'dau': dau,
                'mau': mau,
                'messages_today': messages_today,
                'messages_30d': messages_30d
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting analytics overview: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/analytics/revenue', methods=['GET'])
@jwt_required
def get_revenue_analytics():
    """Revenue analytics: MRR, plan distribution, churn"""
    try:
        # TODO: Implement when billing/plan columns are added to Workspace model
        
        return jsonify({
            'message': 'Revenue analytics not yet implemented',
            'note': 'Add plan, mrr, billing_status columns to Workspace model first'
        }), 501
        
    except Exception as e:
        logger.error(f"Error getting revenue analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ═══ IMPERSONATION ═══

@bp.route('/impersonate/<int:workspace_id>', methods=['POST'])
@jwt_required
def impersonate_workspace(workspace_id):
    """Generate impersonation token for workspace (1 hour validity)"""
    try:
        workspace = Workspace.query.get(workspace_id)
        
        if not workspace:
            return jsonify({'error': 'Workspace not found'}), 404
        
        # Get client IP
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        # Create impersonation log
        impersonate_log = ImpersonateLog(
            super_admin_id=request.super_admin.id,
            workspace_id=workspace_id,
            started_at=datetime.utcnow(),
            ip_address=ip_address
        )
        db.session.add(impersonate_log)
        db.session.commit()
        
        # Generate impersonation token (1 hour expiry)
        token = jwt.encode({
            'impersonate_log_id': impersonate_log.id,
            'workspace_id': workspace_id,
            'super_admin_id': request.super_admin.id,
            'exp': datetime.utcnow() + timedelta(hours=1)
        }, JWT_SECRET, algorithm='HS256')
        
        logger.warning(f"Impersonation started: super admin {request.super_admin.email} → workspace {workspace_id}")
        
        return jsonify({
            'token': token,
            'workspace': {
                'id': workspace.id,
                'company_name': workspace.company_name
            },
            'expires_in': 3600,
            'impersonate_log_id': impersonate_log.id
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating impersonation token: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/impersonate', methods=['DELETE'])
@jwt_required
def end_impersonation():
    """End current impersonation session"""
    data = request.get_json()
    
    if not data or not data.get('impersonate_log_id'):
        return jsonify({'error': 'impersonate_log_id required'}), 400
    
    try:
        impersonate_log = ImpersonateLog.query.get(data['impersonate_log_id'])
        
        if not impersonate_log:
            return jsonify({'error': 'Impersonation log not found'}), 404
        
        if impersonate_log.super_admin_id != request.super_admin.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # End impersonation
        impersonate_log.ended_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Impersonation ended: log_id {impersonate_log.id}")
        
        return jsonify({
            'message': 'Impersonation ended',
            'duration_seconds': (impersonate_log.ended_at - impersonate_log.started_at).total_seconds()
        }), 200
        
    except Exception as e:
        logger.error(f"Error ending impersonation: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500
