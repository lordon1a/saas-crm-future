from datetime import datetime, timedelta

from models import Conversation, Customer, Message, Note, db
from models_crm import Activity, Contact, Company, Deal, GoogleIntegration, QuickBooksIntegration, Task


class SystemHealthService:
    @staticmethod
    def _activity_coverage(workspace_id, days=30):
        since = datetime.utcnow() - timedelta(days=days)
        rows = db.session.query(
            Activity.activity_type,
            db.func.count(Activity.id).label('count'),
        ).filter(
            Activity.workspace_id == workspace_id,
            Activity.created_at >= since,
        ).group_by(Activity.activity_type).all()

        by_type = {r.activity_type: int(r.count) for r in rows}
        required_types = {'system', 'task', 'email', 'note'}
        missing = sorted([t for t in required_types if by_type.get(t, 0) == 0])
        return {
            'days': days,
            'by_type': by_type,
            'missing_required_types': missing,
            'ok': len(missing) == 0,
        }

    @staticmethod
    def _relational_integrity(workspace_id):
        # Orphan checks (basic but effective)
        orphan_messages = db.session.query(Message.id).outerjoin(
            Conversation, Message.conversation_id == Conversation.id
        ).filter(
            Conversation.id.is_(None)
        ).count()

        orphan_notes = db.session.query(Note.id).outerjoin(
            Conversation, Note.conversation_id == Conversation.id
        ).filter(
            Conversation.id.is_(None)
        ).count()

        cross_workspace_conversations = db.session.query(Conversation.id).join(
            Customer, Conversation.customer_id == Customer.id
        ).filter(
            Conversation.workspace_id == workspace_id,
            Customer.workspace_id != workspace_id,
        ).count()

        cross_workspace_deals = db.session.query(Deal.id).join(
            Company, Deal.company_id == Company.id
        ).filter(
            Deal.workspace_id == workspace_id,
            Company.workspace_id != workspace_id,
        ).count()

        totals = {
            'orphan_messages': int(orphan_messages),
            'orphan_notes': int(orphan_notes),
            'cross_workspace_conversations': int(cross_workspace_conversations),
            'cross_workspace_deals': int(cross_workspace_deals),
        }
        return {
            'ok': all(v == 0 for v in totals.values()),
            'details': totals,
        }

    @staticmethod
    def _integration_health(workspace_id):
        google_active = GoogleIntegration.query.filter_by(workspace_id=workspace_id, is_active=True).count()
        quickbooks_active = QuickBooksIntegration.query.filter_by(workspace_id=workspace_id, is_active=True).count()
        return {
            'google_active_connections': int(google_active),
            'quickbooks_active_connections': int(quickbooks_active),
            'ok': True,
        }

    @staticmethod
    def _workspace_stats(workspace_id):
        return {
            'contacts': Contact.query.filter_by(workspace_id=workspace_id).count(),
            'companies': Company.query.filter_by(workspace_id=workspace_id).count(),
            'deals': Deal.query.filter_by(workspace_id=workspace_id).count(),
            'tasks': Task.query.filter_by(workspace_id=workspace_id).count(),
            'conversations': Conversation.query.filter_by(workspace_id=workspace_id).count(),
        }

    @staticmethod
    def generate_report(workspace_id, days=30):
        activity = SystemHealthService._activity_coverage(workspace_id, days)
        integrity = SystemHealthService._relational_integrity(workspace_id)
        integrations = SystemHealthService._integration_health(workspace_id)
        stats = SystemHealthService._workspace_stats(workspace_id)

        checks = {
            'activity_coverage': activity,
            'relational_integrity': integrity,
            'integration_health': integrations,
        }
        overall_ok = all(section.get('ok', False) for section in checks.values())
        return {
            'workspace_id': workspace_id,
            'generated_at': datetime.utcnow().isoformat(),
            'overall_ok': overall_ok,
            'checks': checks,
            'stats': stats,
        }
