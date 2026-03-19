import unittest
from datetime import datetime, timedelta

from flask import Flask

from config import Config
from models import Conversation, Customer, User, Workspace, db
import models_crm  # noqa: F401
from models_crm import Activity, EmailSync, EmailTracking, GoogleIntegration, OutboundEmail
from services.email_hub_service import EmailHubService


class TestPhase11Email(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(cls.app)

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self._old_provider = getattr(Config, 'EMAIL_PROVIDER', 'smtp')
        self._old_app_base_url = getattr(Config, 'APP_BASE_URL', 'http://localhost:5000')
        Config.EMAIL_PROVIDER = 'log'
        Config.APP_BASE_URL = 'http://localhost:5000'

        ws = Workspace(company_name='Phase11 Test Workspace')
        db.session.add(ws)
        db.session.flush()

        user = User(
            workspace_id=ws.id,
            name='Email Admin',
            email='email.admin@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add(user)
        db.session.flush()

        customer = Customer(
            workspace_id=ws.id,
            phone_number='+905001112233',
            profile_name='Ada Lovelace',
            email='ada@example.com',
        )
        db.session.add(customer)
        db.session.flush()

        conv = Conversation(
            workspace_id=ws.id,
            customer_id=customer.id,
            status='open',
            tags='yeni_siparis',
            last_message_at=datetime.utcnow() - timedelta(minutes=20),
        )
        db.session.add(conv)
        db.session.commit()

        self.workspace_id = ws.id
        self.user_id = user.id
        self.customer_id = customer.id
        self.conversation_id = conv.id

    def tearDown(self):
        Config.EMAIL_PROVIDER = self._old_provider
        Config.APP_BASE_URL = self._old_app_base_url
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_property_56_template_variable_substitution(self):
        row = EmailHubService.create_template(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            name='Follow-up',
            subject_template='Hi {{ customer_name }}',
            body_template='Deal value: {{ deal_value }}',
        )

        rendered = EmailHubService.render_template_preview(
            workspace_id=self.workspace_id,
            template_id=row.id,
            variables={'customer_name': 'Ada', 'deal_value': '1000 USD'},
        )
        self.assertEqual(rendered['subject'], 'Hi Ada')
        self.assertIn('1000 USD', rendered['body'])

        with self.assertRaises(ValueError):
            EmailHubService.render_template_preview(
                workspace_id=self.workspace_id,
                template_id=row.id,
                variables={'customer_name': 'Ada'},
            )

    def test_property_57_unified_inbox_aggregation(self):
        integration = GoogleIntegration(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            google_email='agent@example.com',
            access_token='encrypted-token',
            refresh_token='encrypted-refresh',
            is_active=True,
        )
        db.session.add(integration)
        db.session.flush()

        synced = EmailSync(
            workspace_id=self.workspace_id,
            google_integration_id=integration.id,
            gmail_message_id='gmail-1',
            thread_id='thread-1',
            subject='Inbound Proposal',
            from_email='lead@example.com',
            body_snippet='Can we discuss pricing?',
            received_at=datetime.utcnow() - timedelta(minutes=5),
            contact_id=None,
            company_id=None,
            is_sent=False,
        )
        db.session.add(synced)
        db.session.commit()

        payload = EmailHubService.get_unified_inbox(self.workspace_id, channel='all', limit=20, offset=0)
        self.assertGreaterEqual(payload['counts']['total'], 2)
        self.assertGreaterEqual(payload['counts']['whatsapp'], 1)
        self.assertGreaterEqual(payload['counts']['email'], 1)
        self.assertIn(payload['items'][0]['item_type'], {'email', 'whatsapp'})

        email_only = EmailHubService.get_unified_inbox(self.workspace_id, channel='email', limit=20, offset=0)
        self.assertTrue(all(item['item_type'] == 'email' for item in email_only['items']))

    def test_property_58_email_sending_and_logging(self):
        result = EmailHubService.queue_outbound_email(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            to_email='client@example.com',
            subject='Phase 11 update',
            body_text='Hello from CRM',
            body_html='<p>Hello from CRM</p>',
            contact_id=self.customer_id,
        )

        self.assertEqual(result['status'], 'sent')
        self.assertTrue(result['tracking_id'])

        outbound = OutboundEmail.query.filter_by(workspace_id=self.workspace_id).first()
        self.assertIsNotNone(outbound)
        self.assertEqual(outbound.status, 'sent')

        tracking = EmailTracking.query.filter_by(tracking_id=result['tracking_id']).first()
        self.assertIsNotNone(tracking)

        activity = Activity.query.filter_by(workspace_id=self.workspace_id, activity_type='email').first()
        self.assertIsNotNone(activity)


if __name__ == '__main__':
    unittest.main()
