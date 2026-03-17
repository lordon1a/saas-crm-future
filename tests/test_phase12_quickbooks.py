import unittest
from datetime import datetime
from decimal import Decimal

from flask import Flask

from models import Workspace, User, db
import models_crm  # noqa: F401
from models_crm import Company, Deal, DealStage, Pipeline, QuickBooksSyncError
from services.quickbooks_service import QuickBooksService


class TestPhase12QuickBooks(unittest.TestCase):
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

        ws = Workspace(company_name='QB Test Workspace')
        db.session.add(ws)
        db.session.flush()

        user = User(
            workspace_id=ws.id,
            name='QB User',
            email='qb.user@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add(user)
        db.session.flush()

        company = Company(workspace_id=ws.id, name='Acme Inc')
        db.session.add(company)
        db.session.flush()

        pipeline = Pipeline(workspace_id=ws.id, name='Sales', is_default=True)
        db.session.add(pipeline)
        db.session.flush()

        stage = DealStage(pipeline_id=pipeline.id, name='Closed Won', order=1, probability=1.0)
        db.session.add(stage)
        db.session.flush()

        deal = Deal(
            workspace_id=ws.id,
            name='Enterprise Plan',
            company_id=company.id,
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            owner_id=user.id,
            status='won',
            value=Decimal('12500.00'),
            expected_close_date=datetime.utcnow().date(),
            closed_at=datetime.utcnow(),
        )
        db.session.add(deal)
        db.session.commit()

        self.workspace_id = ws.id
        self.user_id = user.id
        self.deal_id = deal.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_property_59_quickbooks_sync_error_logging(self):
        row = QuickBooksService.log_sync_error(
            workspace_id=self.workspace_id,
            operation='invoice.sync',
            error_message='Simulated sync failure',
            retry_count=1,
            will_retry=True,
            http_status=500,
        )

        self.assertIsNotNone(row.id)
        self.assertTrue(row.correlation_id)

        found = QuickBooksSyncError.query.filter_by(id=row.id).first()
        self.assertIsNotNone(found)
        self.assertEqual(found.operation, 'invoice.sync')
        self.assertEqual(found.http_status, 500)
        self.assertTrue(found.will_retry)

    def test_create_invoice_for_won_deal_without_connection_logs_error(self):
        invoice = QuickBooksService.create_invoice_for_deal(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            deal_id=self.deal_id,
        )
        self.assertIsNotNone(invoice.id)
        self.assertEqual(invoice.sync_status, 'failed')
        self.assertIn('not connected', (invoice.error_message or '').lower())

        err_count = QuickBooksSyncError.query.filter_by(
            workspace_id=self.workspace_id,
            invoice_id=invoice.id,
            operation='invoice.create',
        ).count()
        self.assertGreaterEqual(err_count, 1)


if __name__ == '__main__':
    unittest.main()
