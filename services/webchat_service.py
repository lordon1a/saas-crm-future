"""Webchat business logic service."""
from datetime import datetime
import secrets


ALLOWED_STATUS = {'open', 'assigned', 'closed'}


def _split_name(full_name):
    parts = (full_name or '').strip().split(' ', 1)
    if not parts or not parts[0]:
        return 'Visitor', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], parts[1]


def get_or_create_config(workspace_id):
    from app import db
    from models_crm import WebChatConfig

    cfg = WebChatConfig.query.filter_by(workspace_id=workspace_id).first()
    if cfg:
        return cfg

    cfg = WebChatConfig(workspace_id=workspace_id)
    db.session.add(cfg)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return cfg


def init_public_session(workspace_id, visitor_id=None, source_url=None, name=None, email=None):
    from app import db
    from models_crm import ChatSession, ChatMessage, Contact

    cfg = get_or_create_config(workspace_id)
    if not cfg.is_active:
        raise ValueError('Webchat is disabled for this workspace')

    visitor_id = visitor_id or secrets.token_urlsafe(12)

    session = ChatSession(
        workspace_id=workspace_id,
        visitor_id=visitor_id,
        source_url=source_url,
        status='open',
    )

    if cfg.auto_create_contact and email:
        contact = Contact.query.filter_by(workspace_id=workspace_id, email=email.lower()).first()
        if not contact:
            first_name, last_name = _split_name(name)
            contact = Contact(
                workspace_id=workspace_id,
                first_name=first_name,
                last_name=last_name,
                email=email.lower(),
                lead_source='webchat',
            )
            db.session.add(contact)
            db.session.flush()
        session.contact_id = contact.id

    db.session.add(session)
    db.session.flush()

    welcome = ChatMessage(
        session_id=session.id,
        sender_type='bot',
        content=cfg.welcome_message,
    )
    db.session.add(welcome)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return session


def add_public_message(session_id, content):
    from app import db
    from models_crm import ChatSession, ChatMessage

    chat_session = ChatSession.query.get(session_id)
    if not chat_session:
        raise ValueError('Chat session not found')
    if chat_session.status == 'closed':
        raise ValueError('Chat session already closed')

    msg = ChatMessage(
        session_id=chat_session.id,
        sender_type='visitor',
        content=(content or '').strip(),
    )
    if not msg.content:
        raise ValueError('Message content is required')

    chat_session.last_message_at = datetime.utcnow()
    db.session.add(msg)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return msg


def poll_messages(session_id, since_id=0):
    from models_crm import ChatMessage

    query = ChatMessage.query.filter(
        ChatMessage.session_id == session_id,
        ChatMessage.id > since_id,
    ).order_by(ChatMessage.id.asc())
    return query.all()


def list_open_sessions(workspace_id):
    from models_crm import ChatSession

    return ChatSession.query.filter(
        ChatSession.workspace_id == workspace_id,
        ChatSession.status.in_(['open', 'assigned'])
    ).order_by(ChatSession.last_message_at.desc()).all()


def get_session_messages(workspace_id, session_id):
    from models_crm import ChatSession, ChatMessage

    chat_session = ChatSession.query.filter_by(id=session_id, workspace_id=workspace_id).first()
    if not chat_session:
        return None, []

    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.id.asc()).all()
    return chat_session, messages


def agent_reply(workspace_id, session_id, agent_id, content):
    from app import db
    from models_crm import ChatSession, ChatMessage

    chat_session = ChatSession.query.filter_by(id=session_id, workspace_id=workspace_id).first()
    if not chat_session:
        raise ValueError('Chat session not found')
    if chat_session.status == 'closed':
        raise ValueError('Chat session already closed')

    msg = ChatMessage(
        session_id=session_id,
        sender_type='agent',
        sender_id=agent_id,
        content=(content or '').strip(),
    )
    if not msg.content:
        raise ValueError('Reply content is required')

    if chat_session.status == 'open':
        chat_session.status = 'assigned'
        chat_session.assigned_to = agent_id

    chat_session.last_message_at = datetime.utcnow()
    db.session.add(msg)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return msg


def close_session(workspace_id, session_id):
    from app import db
    from models_crm import ChatSession, Activity

    chat_session = ChatSession.query.filter_by(id=session_id, workspace_id=workspace_id).first()
    if not chat_session:
        raise ValueError('Chat session not found')

    chat_session.status = 'closed'
    chat_session.last_message_at = datetime.utcnow()

    activity = Activity(
        workspace_id=workspace_id,
        contact_id=chat_session.contact_id,
        activity_type='webchat_closed',
        description='Webchat session closed',
        notes=f'Visitor: {chat_session.visitor_id}',
        user_id=chat_session.assigned_to,
    )
    db.session.add(activity)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return chat_session


def update_config(workspace_id, updates):
    from app import db

    cfg = get_or_create_config(workspace_id)

    for field in [
        'widget_title', 'welcome_message', 'primary_color', 'bot_name',
        'collect_name', 'collect_email', 'is_active', 'auto_create_contact'
    ]:
        if field in updates:
            setattr(cfg, field, updates[field])

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return cfg
