"""Call logging service."""
from datetime import datetime, timedelta


VALID_DIRECTIONS = {'inbound', 'outbound'}
VALID_OUTCOMES = {'connected', 'no_answer', 'busy', 'left_voicemail', 'wrong_number'}


def _create_activity_for_call(call_log):
    from app import db
    from models_crm import Activity

    if not call_log.contact_id:
        return

    activity = Activity(
        workspace_id=call_log.workspace_id,
        contact_id=call_log.contact_id,
        deal_id=call_log.deal_id,
        activity_type='call',
        description=f"Call {call_log.direction}: {call_log.outcome}",
        notes=call_log.notes,
        user_id=call_log.logged_by,
    )
    db.session.add(activity)


def create_call_log(workspace_id, logged_by, payload):
    from app import db
    from models_crm import CallLog

    direction = payload.get('direction', 'outbound')
    if direction not in VALID_DIRECTIONS:
        raise ValueError('Invalid direction')

    outcome = payload.get('outcome', 'connected')
    if outcome not in VALID_OUTCOMES:
        raise ValueError('Invalid outcome')

    phone = (payload.get('phone_number') or '').strip()
    if not phone:
        raise ValueError('phone_number is required')

    called_at = payload.get('called_at')
    if called_at and isinstance(called_at, str):
        called_at = datetime.fromisoformat(called_at.replace('Z', '+00:00'))

    call_log = CallLog(
        workspace_id=workspace_id,
        contact_id=payload.get('contact_id'),
        deal_id=payload.get('deal_id'),
        logged_by=logged_by,
        direction=direction,
        phone_number=phone,
        duration_seconds=int(payload.get('duration_seconds') or 0),
        outcome=outcome,
        notes=payload.get('notes'),
        recording_url=payload.get('recording_url'),
        external_call_id=payload.get('external_call_id'),
        called_at=called_at or datetime.utcnow(),
    )

    db.session.add(call_log)
    db.session.flush()
    _create_activity_for_call(call_log)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return call_log


def list_call_logs(workspace_id, page=1, per_page=50, contact_id=None):
    from models_crm import CallLog

    query = CallLog.query.filter_by(workspace_id=workspace_id)
    if contact_id:
        query = query.filter_by(contact_id=contact_id)

    total = query.count()
    items = query.order_by(CallLog.called_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def get_call_log(workspace_id, call_id):
    from models_crm import CallLog

    return CallLog.query.filter_by(id=call_id, workspace_id=workspace_id).first()


def update_call_log(workspace_id, call_id, updates):
    from app import db

    call_log = get_call_log(workspace_id, call_id)
    if not call_log:
        return None

    if 'notes' in updates:
        call_log.notes = updates['notes']
    if 'outcome' in updates and updates['outcome'] in VALID_OUTCOMES:
        call_log.outcome = updates['outcome']
    if 'recording_url' in updates:
        call_log.recording_url = updates['recording_url']

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return call_log


def delete_call_log(workspace_id, call_id):
    from app import db

    call_log = get_call_log(workspace_id, call_id)
    if not call_log:
        return False

    db.session.delete(call_log)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return True


def create_from_twilio_event(workspace_id, logged_by, payload):
    duration = int(payload.get('CallDuration') or 0)
    status = (payload.get('CallStatus') or '').lower()

    outcome = 'connected'
    if status in {'busy'}:
        outcome = 'busy'
    elif status in {'no-answer', 'failed'}:
        outcome = 'no_answer'

    data = {
        'direction': 'inbound' if 'inbound' in (payload.get('Direction') or '') else 'outbound',
        'phone_number': payload.get('From') or payload.get('To') or 'unknown',
        'duration_seconds': duration,
        'outcome': outcome,
        'external_call_id': payload.get('CallSid'),
        'recording_url': payload.get('RecordingUrl'),
        'notes': 'Twilio webhook auto-log',
        'called_at': datetime.utcnow().isoformat(),
    }
    return create_call_log(workspace_id, logged_by, data)


def calls_summary(workspace_id, days=7):
    from models_crm import CallLog

    since = datetime.utcnow() - timedelta(days=days)
    rows = CallLog.query.filter(
        CallLog.workspace_id == workspace_id,
        CallLog.called_at >= since,
    ).all()

    total = len(rows)
    connected = len([r for r in rows if r.outcome == 'connected'])
    total_duration = sum(r.duration_seconds or 0 for r in rows)
    return {
        'days': days,
        'total_calls': total,
        'connected_calls': connected,
        'connection_rate': round((connected / total) * 100, 1) if total else 0,
        'total_duration_seconds': total_duration,
    }
