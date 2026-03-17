import unittest
from datetime import datetime, timedelta

from flask import Flask

from models import Conversation, Customer, Message, Note, User, Workspace, db
import models_crm  # noqa: F401
from models_crm import Activity, Company, Contact, Deal, DealStage, Pipeline
from services.system_health_service import SystemHealthService


class TestPhase14SystemHealth(unittest.TestCase):
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

        ws = Workspace(company_name='Health WS')
        db.session.add(ws)
        db.session.flush()

        user = User(
            workspace_id=ws.id,
            name='Health User',
            email='health@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add(user)
        db.session.flush()

        customer = Customer(workspace_id=ws.id, phone_number='+905001234567', profile_name='C1')
        db.session.add(customer)
        db.session.flush()

        conv = Conversation(
            workspace_id=ws.id,
            customer_id=customer.id,
            status='open',
            last_message_at=datetime.utcnow(),
        )
        db.session.add(conv)
        db.session.flush()

        db.session.add(Message(conversation_id=conv.id, sender_type='customer', message_body='Hello'))
        db.session.add(Note(conversation_id=conv.id, user_id=user.id, content='N1', is_internal=False))

        pipeline = Pipeline(workspace_id=ws.id, name='Sales', is_default=True)
        db.session.add(pipeline)
        db.session.flush()

        stage = DealStage(pipeline_id=pipeline.id, name='S1', order=1, probability=0.5)
        db.session.add(stage)
        db.session.flush()

        company = Company(workspace_id=ws.id, name='Acme')
        db.session.add(company)
        db.session.flush()

        contact = Contact(workspace_id=ws.id, first_name='A', last_name='B', company_id=company.id)
        db.session.add(contact)

        deal = Deal(
            workspace_id=ws.id,
            name='D1',
            company_id=company.id,
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            owner_id=user.id,
            status='open',
            value=100,
        )
        db.session.add(deal)

        now = datetime.utcnow()
        db.session.add(Activity(workspace_id=ws.id, activity_type='system', created_at=now - timedelta(days=1)))
        db.session.add(Activity(workspace_id=ws.id, activity_type='task', created_at=now - timedelta(hours=12)))
        db.session.add(Activity(workspace_id=ws.id, activity_type='email', created_at=now - timedelta(hours=6)))
        db.session.add(Activity(workspace_id=ws.id, activity_type='note', created_at=now - timedelta(hours=3)))
        db.session.commit()

        self.workspace_id = ws.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_generate_report_shape(self):
        report = SystemHealthService.generate_report(self.workspace_id, days=30)
        self.assertIn('overall_ok', report)
        self.assertIn('checks', report)
        self.assertIn('stats', report)

    def test_activity_coverage_ok(self):
        report = SystemHealthService.generate_report(self.workspace_id, days=30)
        coverage = report['checks']['activity_coverage']
        self.assertTrue(coverage['ok'])
        self.assertEqual(coverage['missing_required_types'], [])

    def test_relational_integrity_ok(self):
        report = SystemHealthService.generate_report(self.workspace_id, days=30)
        integrity = report['checks']['relational_integrity']
        self.assertTrue(integrity['ok'])
        for value in integrity['details'].values():
            self.assertEqual(value, 0)


if __name__ == '__main__':
    unittest.main()
