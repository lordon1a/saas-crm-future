"""
Automation API Routes
Otomasyon yönetimi için API endpoint'leri
"""
from flask import Blueprint, request, jsonify, session
from models import db
from models_automation import (
    AutomationRule, AutoReply, AssignmentRule, 
    ScheduledMessage, WorkflowTemplate, AutomationExecution
)
from functools import wraps
import json
from datetime import datetime

bp = Blueprint('automation', __name__, url_prefix='/api/automation')

def login_required_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        if not session.get('workspace_id'):
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated


# ═══ AUTOMATION RULES ═══

@bp.route('/rules', methods=['GET'])
@login_required_api
def get_automation_rules():
    """Tüm otomasyon kurallarını listele"""
    workspace_id = session.get('workspace_id')
    rules = AutomationRule.query.filter_by(workspace_id=workspace_id).order_by(AutomationRule.created_at.desc()).all()
    
    result = []
    for rule in rules:
        result.append({
            'id': rule.id,
            'name': rule.name,
            'description': rule.description,
            'is_active': rule.is_active,
            'trigger_type': rule.trigger_type,
            'trigger_config': json.loads(rule.trigger_config) if rule.trigger_config else {},
            'conditions': json.loads(rule.conditions) if rule.conditions else {},
            'actions': json.loads(rule.actions) if rule.actions else [],
            'execution_count': rule.execution_count,
            'last_executed_at': rule.last_executed_at.isoformat() if rule.last_executed_at else None,
            'created_at': rule.created_at.isoformat()
        })
    
    return jsonify(result), 200


@bp.route('/rules', methods=['POST'])
@login_required_api
def create_automation_rule():
    """Yeni otomasyon kuralı oluştur"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Kural adı zorunludur'}), 400
    
    rule = AutomationRule(
        workspace_id=workspace_id,
        name=name,
        description=data.get('description', ''),
        is_active=data.get('is_active', True),
        trigger_type=data.get('trigger_type', 'new_conversation'),
        trigger_config=json.dumps(data.get('trigger_config', {})),
        conditions=json.dumps(data.get('conditions', {})),
        actions=json.dumps(data.get('actions', [])),
        created_by=user_id
    )
    
    db.session.add(rule)
    db.session.commit()
    
    return jsonify({
        'id': rule.id,
        'name': rule.name,
        'status': 'created'
    }), 201


@bp.route('/rules/<int:rule_id>', methods=['PUT'])
@login_required_api
def update_automation_rule(rule_id):
    """Otomasyon kuralını güncelle"""
    workspace_id = session.get('workspace_id')
    rule = AutomationRule.query.filter_by(id=rule_id, workspace_id=workspace_id).first()
    
    if not rule:
        return jsonify({'error': 'Kural bulunamadı'}), 404
    
    data = request.get_json()
    
    if 'name' in data:
        rule.name = data['name'].strip()
    if 'description' in data:
        rule.description = data['description']
    if 'is_active' in data:
        rule.is_active = data['is_active']
    if 'trigger_config' in data:
        rule.trigger_config = json.dumps(data['trigger_config'])
    if 'conditions' in data:
        rule.conditions = json.dumps(data['conditions'])
    if 'actions' in data:
        rule.actions = json.dumps(data['actions'])
    
    rule.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'status': 'updated'}), 200


@bp.route('/rules/<int:rule_id>', methods=['DELETE'])
@login_required_api
def delete_automation_rule(rule_id):
    """Otomasyon kuralını sil"""
    workspace_id = session.get('workspace_id')
    rule = AutomationRule.query.filter_by(id=rule_id, workspace_id=workspace_id).first()
    
    if not rule:
        return jsonify({'error': 'Kural bulunamadı'}), 404
    
    db.session.delete(rule)
    db.session.commit()
    
    return jsonify({'status': 'deleted'}), 200


@bp.route('/rules/<int:rule_id>/toggle', methods=['POST'])
@login_required_api
def toggle_automation_rule(rule_id):
    """Otomasyon kuralını aktif/pasif yap"""
    workspace_id = session.get('workspace_id')
    rule = AutomationRule.query.filter_by(id=rule_id, workspace_id=workspace_id).first()
    
    if not rule:
        return jsonify({'error': 'Kural bulunamadı'}), 404
    
    rule.is_active = not rule.is_active
    db.session.commit()
    
    return jsonify({'status': 'toggled', 'is_active': rule.is_active}), 200


# ═══ AUTO REPLIES ═══

@bp.route('/auto-replies', methods=['GET'])
@login_required_api
def get_auto_replies():
    """Tüm otomatik yanıtları listele"""
    workspace_id = session.get('workspace_id')
    replies = AutoReply.query.filter_by(workspace_id=workspace_id).order_by(AutoReply.created_at.desc()).all()
    
    result = []
    for reply in replies:
        result.append({
            'id': reply.id,
            'name': reply.name,
            'is_active': reply.is_active,
            'keywords': reply.keywords,
            'match_type': reply.match_type,
            'case_sensitive': reply.case_sensitive,
            'reply_message': reply.reply_message,
            'reply_delay': reply.reply_delay,
            'conditions': json.loads(reply.conditions) if reply.conditions else {},
            'trigger_count': reply.trigger_count,
            'last_triggered_at': reply.last_triggered_at.isoformat() if reply.last_triggered_at else None,
            'created_at': reply.created_at.isoformat()
        })
    
    return jsonify(result), 200


@bp.route('/auto-replies', methods=['POST'])
@login_required_api
def create_auto_reply():
    """Yeni otomatik yanıt oluştur"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    name = data.get('name', '').strip()
    keywords = data.get('keywords', '').strip()
    reply_message = data.get('reply_message', '').strip()
    
    if not name or not keywords or not reply_message:
        return jsonify({'error': 'Ad, anahtar kelimeler ve yanıt mesajı zorunludur'}), 400
    
    reply = AutoReply(
        workspace_id=workspace_id,
        name=name,
        is_active=data.get('is_active', True),
        keywords=keywords,
        match_type=data.get('match_type', 'contains'),
        case_sensitive=data.get('case_sensitive', False),
        reply_message=reply_message,
        reply_delay=data.get('reply_delay', 0),
        conditions=json.dumps(data.get('conditions', {})),
        created_by=user_id
    )
    
    db.session.add(reply)
    db.session.commit()
    
    return jsonify({
        'id': reply.id,
        'name': reply.name,
        'status': 'created'
    }), 201


@bp.route('/auto-replies/<int:reply_id>', methods=['PUT'])
@login_required_api
def update_auto_reply(reply_id):
    """Otomatik yanıtı güncelle"""
    workspace_id = session.get('workspace_id')
    reply = AutoReply.query.filter_by(id=reply_id, workspace_id=workspace_id).first()
    
    if not reply:
        return jsonify({'error': 'Otomatik yanıt bulunamadı'}), 404
    
    data = request.get_json()
    
    if 'name' in data:
        reply.name = data['name'].strip()
    if 'is_active' in data:
        reply.is_active = data['is_active']
    if 'keywords' in data:
        reply.keywords = data['keywords'].strip()
    if 'match_type' in data:
        reply.match_type = data['match_type']
    if 'case_sensitive' in data:
        reply.case_sensitive = data['case_sensitive']
    if 'reply_message' in data:
        reply.reply_message = data['reply_message'].strip()
    if 'reply_delay' in data:
        reply.reply_delay = data['reply_delay']
    if 'conditions' in data:
        reply.conditions = json.dumps(data['conditions'])
    
    reply.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'status': 'updated'}), 200


@bp.route('/auto-replies/<int:reply_id>', methods=['DELETE'])
@login_required_api
def delete_auto_reply(reply_id):
    """Otomatik yanıtı sil"""
    workspace_id = session.get('workspace_id')
    reply = AutoReply.query.filter_by(id=reply_id, workspace_id=workspace_id).first()
    
    if not reply:
        return jsonify({'error': 'Otomatik yanıt bulunamadı'}), 404
    
    db.session.delete(reply)
    db.session.commit()
    
    return jsonify({'status': 'deleted'}), 200


# ═══ ASSIGNMENT RULES ═══

@bp.route('/assignment-rules', methods=['GET'])
@login_required_api
def get_assignment_rules():
    """Tüm atama kurallarını listele"""
    workspace_id = session.get('workspace_id')
    rules = AssignmentRule.query.filter_by(workspace_id=workspace_id).order_by(AssignmentRule.priority.desc()).all()
    
    result = []
    for rule in rules:
        result.append({
            'id': rule.id,
            'name': rule.name,
            'is_active': rule.is_active,
            'priority': rule.priority,
            'conditions': json.loads(rule.conditions) if rule.conditions else {},
            'assignment_type': rule.assignment_type,
            'assignment_config': json.loads(rule.assignment_config) if rule.assignment_config else {},
            'assignment_count': rule.assignment_count,
            'last_assigned_at': rule.last_assigned_at.isoformat() if rule.last_assigned_at else None,
            'created_at': rule.created_at.isoformat()
        })
    
    return jsonify(result), 200


@bp.route('/assignment-rules', methods=['POST'])
@login_required_api
def create_assignment_rule():
    """Yeni atama kuralı oluştur"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    name = data.get('name', '').strip()
    assignment_type = data.get('assignment_type', '').strip()
    
    if not name or not assignment_type:
        return jsonify({'error': 'Ad ve atama tipi zorunludur'}), 400
    
    rule = AssignmentRule(
        workspace_id=workspace_id,
        name=name,
        is_active=data.get('is_active', True),
        priority=data.get('priority', 0),
        conditions=json.dumps(data.get('conditions', {})),
        assignment_type=assignment_type,
        assignment_config=json.dumps(data.get('assignment_config', {})),
        created_by=user_id
    )
    
    db.session.add(rule)
    db.session.commit()
    
    return jsonify({
        'id': rule.id,
        'name': rule.name,
        'status': 'created'
    }), 201


@bp.route('/assignment-rules/<int:rule_id>', methods=['PUT'])
@login_required_api
def update_assignment_rule(rule_id):
    """Atama kuralını güncelle"""
    workspace_id = session.get('workspace_id')
    rule = AssignmentRule.query.filter_by(id=rule_id, workspace_id=workspace_id).first()
    
    if not rule:
        return jsonify({'error': 'Atama kuralı bulunamadı'}), 404
    
    data = request.get_json()
    
    if 'name' in data:
        rule.name = data['name'].strip()
    if 'is_active' in data:
        rule.is_active = data['is_active']
    if 'priority' in data:
        rule.priority = data['priority']
    if 'conditions' in data:
        rule.conditions = json.dumps(data['conditions'])
    if 'assignment_type' in data:
        rule.assignment_type = data['assignment_type']
    if 'assignment_config' in data:
        rule.assignment_config = json.dumps(data['assignment_config'])
    
    rule.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'status': 'updated'}), 200


@bp.route('/assignment-rules/<int:rule_id>', methods=['DELETE'])
@login_required_api
def delete_assignment_rule(rule_id):
    """Atama kuralını sil"""
    workspace_id = session.get('workspace_id')
    rule = AssignmentRule.query.filter_by(id=rule_id, workspace_id=workspace_id).first()
    
    if not rule:
        return jsonify({'error': 'Atama kuralı bulunamadı'}), 404
    
    db.session.delete(rule)
    db.session.commit()
    
    return jsonify({'status': 'deleted'}), 200


# ═══ SCHEDULED MESSAGES ═══

@bp.route('/scheduled-messages', methods=['GET'])
@login_required_api
def get_scheduled_messages():
    """Zamanlanmış mesajları listele"""
    workspace_id = session.get('workspace_id')
    status = request.args.get('status', 'pending')
    
    query = ScheduledMessage.query.filter_by(workspace_id=workspace_id)
    if status:
        query = query.filter_by(status=status)
    
    messages = query.order_by(ScheduledMessage.scheduled_at.asc()).all()
    
    result = []
    for msg in messages:
        result.append({
            'id': msg.id,
            'target_type': msg.target_type,
            'target_id': msg.target_id,
            'target_segment': msg.target_segment,
            'message_body': msg.message_body,
            'schedule_type': msg.schedule_type,
            'scheduled_at': msg.scheduled_at.isoformat(),
            'recurrence_pattern': msg.recurrence_pattern,
            'status': msg.status,
            'sent_at': msg.sent_at.isoformat() if msg.sent_at else None,
            'created_at': msg.created_at.isoformat()
        })
    
    return jsonify(result), 200


@bp.route('/scheduled-messages', methods=['POST'])
@login_required_api
def create_scheduled_message():
    """Yeni zamanlanmış mesaj oluştur"""
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    message_body = data.get('message_body', '').strip()
    scheduled_at = data.get('scheduled_at')
    
    if not message_body or not scheduled_at:
        return jsonify({'error': 'Mesaj içeriği ve zamanlama zorunludur'}), 400
    
    try:
        scheduled_datetime = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
    except:
        return jsonify({'error': 'Geçersiz tarih formatı'}), 400
    
    msg = ScheduledMessage(
        workspace_id=workspace_id,
        target_type=data.get('target_type', 'conversation'),
        target_id=data.get('target_id'),
        target_segment=data.get('target_segment'),
        message_body=message_body,
        template_id=data.get('template_id'),
        schedule_type=data.get('schedule_type', 'once'),
        scheduled_at=scheduled_datetime,
        recurrence_pattern=data.get('recurrence_pattern'),
        recurrence_config=json.dumps(data.get('recurrence_config', {})),
        created_by=user_id
    )
    
    db.session.add(msg)
    db.session.commit()
    
    return jsonify({
        'id': msg.id,
        'status': 'scheduled'
    }), 201


@bp.route('/scheduled-messages/<int:msg_id>', methods=['DELETE'])
@login_required_api
def cancel_scheduled_message(msg_id):
    """Zamanlanmış mesajı iptal et"""
    workspace_id = session.get('workspace_id')
    msg = ScheduledMessage.query.filter_by(id=msg_id, workspace_id=workspace_id).first()
    
    if not msg:
        return jsonify({'error': 'Mesaj bulunamadı'}), 404
    
    if msg.status != 'pending':
        return jsonify({'error': 'Sadece bekleyen mesajlar iptal edilebilir'}), 400
    
    msg.status = 'cancelled'
    db.session.commit()
    
    return jsonify({'status': 'cancelled'}), 200


# ═══ WORKFLOW TEMPLATES ═══

@bp.route('/workflow-templates', methods=['GET'])
@login_required_api
def get_workflow_templates():
    """Workflow şablonlarını listele"""
    templates = WorkflowTemplate.query.order_by(WorkflowTemplate.usage_count.desc()).all()
    
    result = []
    for template in templates:
        result.append({
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'category': template.category,
            'icon': template.icon,
            'is_system': template.is_system,
            'usage_count': template.usage_count
        })
    
    return jsonify(result), 200


# ═══ STATISTICS ═══

@bp.route('/stats', methods=['GET'])
@login_required_api
def get_automation_stats():
    """Otomasyon istatistiklerini getir"""
    workspace_id = session.get('workspace_id')
    
    # Toplam kural sayıları
    total_rules = AutomationRule.query.filter_by(workspace_id=workspace_id).count()
    active_rules = AutomationRule.query.filter_by(workspace_id=workspace_id, is_active=True).count()
    
    total_auto_replies = AutoReply.query.filter_by(workspace_id=workspace_id).count()
    active_auto_replies = AutoReply.query.filter_by(workspace_id=workspace_id, is_active=True).count()
    
    total_assignment_rules = AssignmentRule.query.filter_by(workspace_id=workspace_id).count()
    active_assignment_rules = AssignmentRule.query.filter_by(workspace_id=workspace_id, is_active=True).count()
    
    # Son 30 gün execution sayısı
    from datetime import timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    executions_30d = AutomationExecution.query.join(AutomationRule).filter(
        AutomationRule.workspace_id == workspace_id,
        AutomationExecution.executed_at >= thirty_days_ago
    ).count()
    
    successful_executions = AutomationExecution.query.join(AutomationRule).filter(
        AutomationRule.workspace_id == workspace_id,
        AutomationExecution.executed_at >= thirty_days_ago,
        AutomationExecution.status == 'success'
    ).count()
    
    return jsonify({
        'rules': {
            'total': total_rules,
            'active': active_rules
        },
        'auto_replies': {
            'total': total_auto_replies,
            'active': active_auto_replies
        },
        'assignment_rules': {
            'total': total_assignment_rules,
            'active': active_assignment_rules
        },
        'executions_30d': executions_30d,
        'success_rate': round((successful_executions / executions_30d * 100) if executions_30d > 0 else 0, 1)
    }), 200
