import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import event, inspect, select

from config import Config
from models_crm import Company, Contact, CustomerUser, Document, Task

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return bool(getattr(Config, 'SMTP_HOST', None) and getattr(Config, 'SMTP_FROM_EMAIL', None))


def _portal_base_url() -> str:
    value = (getattr(Config, 'PORTAL_BASE_URL', '') or '').strip().rstrip('/')
    if value:
        return value
    return 'http://localhost:5000/portal'


def _collect_recipient_emails(connection, workspace_id: int, company_id: int) -> list[str]:
    if not workspace_id or not company_id:
        return []

    recipients = set()

    customer_rows = connection.execute(
        select(CustomerUser.email).where(
            CustomerUser.workspace_id == workspace_id,
            CustomerUser.company_id == company_id,
            CustomerUser.is_active.is_(True),
        )
    ).all()

    for row in customer_rows:
        if row[0]:
            recipients.add(row[0].strip().lower())

    contact_rows = connection.execute(
        select(Contact.email).where(
            Contact.workspace_id == workspace_id,
            Contact.company_id == company_id,
            Contact.email.isnot(None),
        )
    ).all()

    for row in contact_rows:
        if row[0]:
            recipients.add(row[0].strip().lower())

    return sorted(email for email in recipients if email)


def _company_name(connection, company_id: int) -> str:
    if not company_id:
        return 'Müşteri'

    row = connection.execute(
        select(Company.name).where(Company.id == company_id)
    ).first()

    if not row or not row[0]:
        return 'Müşteri'
    return row[0]


def _send_email(recipients: list[str], subject: str, body: str):
    if not recipients:
        return

    if not _smtp_configured():
        logger.info('Portal notification skipped: SMTP is not configured')
        return

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = getattr(Config, 'SMTP_FROM_EMAIL')
    message['To'] = ', '.join(recipients)
    message.set_content(body)

    host = getattr(Config, 'SMTP_HOST')
    port = int(getattr(Config, 'SMTP_PORT', 587))
    user = (getattr(Config, 'SMTP_USER', '') or '').strip()
    password = getattr(Config, 'SMTP_PASSWORD', '') or ''
    use_tls = bool(getattr(Config, 'SMTP_TLS', True))

    with smtplib.SMTP(host=host, port=port, timeout=15) as smtp:
        if use_tls:
            smtp.starttls()
        if user:
            smtp.login(user, password)
        smtp.send_message(message)


def _notify_new_task(connection, task: Task):
    if not task.is_customer_facing or not task.company_id:
        return

    recipients = _collect_recipient_emails(connection, task.workspace_id, task.company_id)
    if not recipients:
        return

    company_name = _company_name(connection, task.company_id)
    subject = f'Yeni görev paylaşıldı - {company_name}'
    body = (
        f"Merhaba,\n\n"
        f"Sizinle yeni bir görev paylaşıldı:\n"
        f"- Başlık: {task.title}\n"
        f"- Öncelik: {task.priority}\n"
        f"- Durum: {task.status}\n"
        f"- Son tarih: {task.due_date.isoformat() if task.due_date else 'Belirtilmedi'}\n\n"
        f"Portal üzerinden detayları görüntüleyebilirsiniz:\n"
        f"{_portal_base_url()}/dashboard\n"
    )

    try:
        _send_email(recipients, subject, body)
    except Exception as exc:
        logger.warning('Task notification email failed: %s', exc)


def _notify_new_document(connection, document: Document):
    if not document.is_customer_visible or not document.company_id:
        return

    recipients = _collect_recipient_emails(connection, document.workspace_id, document.company_id)
    if not recipients:
        return

    company_name = _company_name(connection, document.company_id)
    category = (document.category or 'document').strip()
    subject = f'Yeni doküman paylaşıldı - {company_name}'
    body = (
        f"Merhaba,\n\n"
        f"Sizinle yeni bir doküman paylaşıldı:\n"
        f"- Doküman: {document.name}\n"
        f"- Kategori: {category}\n\n"
        f"Portal üzerinden görüntüleyebilir ve indirebilirsiniz:\n"
        f"{_portal_base_url()}/documents\n"
    )

    try:
        _send_email(recipients, subject, body)
    except Exception as exc:
        logger.warning('Document notification email failed: %s', exc)


@event.listens_for(Task, 'after_insert')
def _task_after_insert(mapper, connection, target):
    _notify_new_task(connection, target)


@event.listens_for(Task, 'after_update')
def _task_after_update(mapper, connection, target):
    state = inspect(target)
    history = state.attrs.is_customer_facing.history
    turned_on = history.has_changes() and bool(history.added) and history.added[0] is True
    if turned_on:
        _notify_new_task(connection, target)


@event.listens_for(Document, 'after_insert')
def _document_after_insert(mapper, connection, target):
    _notify_new_document(connection, target)


@event.listens_for(Document, 'after_update')
def _document_after_update(mapper, connection, target):
    state = inspect(target)
    history = state.attrs.is_customer_visible.history
    turned_on = history.has_changes() and bool(history.added) and history.added[0] is True
    if turned_on:
        _notify_new_document(connection, target)
