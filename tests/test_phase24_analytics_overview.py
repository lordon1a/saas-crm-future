import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from flask import Flask

from models import User, Workspace, db
import models_crm  # noqa: F401
from models_crm import Company, Deal, DealStage, Pipeline
import routes.analytics as analytics_routes
from routes.analytics import bp as analytics_bp


class FrozenJan31DateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls(2026, 1, 31, 12, 0, 0)
        return cls(2026, 1, 31, 12, 0, 0, tzinfo=tz)


class TestPhase24AnalyticsOverview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        cls.app.secret_key = 'phase24-analytics-overview'
        db.init_app(cls.app)
        cls.app.register_blueprint(analytics_bp)

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        ws = Workspace(company_name='Phase24 Workspace')
        db.session.add(ws)
        db.session.flush()

        user = User(
            workspace_id=ws.id,
            name='Phase24 User',
            email='phase24-user@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add(user)
        db.session.flush()

        company = Company(
            workspace_id=ws.id,
            name='Phase24 Co',
        )
        db.session.add(company)
        db.session.flush()

        pipeline = Pipeline(
            workspace_id=ws.id,
            name='Sales',
            is_default=True,
        )
        db.session.add(pipeline)
        db.session.flush()

        stage = DealStage(
            pipeline_id=pipeline.id,
            name='Negotiation',
            order=1,
            probability=80,
        )
        db.session.add(stage)
        db.session.flush()

        jan_won = Deal(
            workspace_id=ws.id,
            name='Jan Won',
            company_id=company.id,
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            owner_id=user.id,
            value=12000,
            status='won',
            closed_at=datetime(2026, 1, 15, tzinfo=UTC),
        )
        dec_won = Deal(
            workspace_id=ws.id,
            name='Dec Won',
            company_id=company.id,
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            owner_id=user.id,
            value=5000,
            status='won',
            closed_at=datetime(2025, 12, 20, tzinfo=UTC),
        )
        open_deal = Deal(
            workspace_id=ws.id,
            name='Open Deal',
            company_id=company.id,
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            owner_id=user.id,
            value=999,
            status='open',
        )

        db.session.add_all([jan_won, dec_won, open_deal])
        db.session.commit()

        self.workspace_id = ws.id
        self.user_id = user.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self, client):
        with client.session_transaction() as sess:
            sess['workspace_id'] = self.workspace_id
            sess['user_id'] = self.user_id

    def test_monthly_performance_handles_month_end_window(self):
        with patch('routes.analytics.datetime', FrozenJan31DateTime):
            payload = analytics_routes._get_monthly_performance(self.workspace_id, months=6)

        months = payload.get('months', [])
        self.assertEqual(len(months), 6)
        self.assertEqual(months[0]['month'], '2025-08')
        self.assertEqual(months[-1]['month'], '2026-01')

        by_month = {row['month']: row['revenue'] for row in months}
        self.assertEqual(by_month['2025-12'], 5000.0)
        self.assertEqual(by_month['2026-01'], 12000.0)

    def test_overview_endpoint_stable_at_month_end(self):
        with patch('routes.analytics.datetime', FrozenJan31DateTime):
            with self.app.test_client() as client:
                self._login(client)
                response = client.get('/api/v1/analytics/overview')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get('success'))
        monthly = payload.get('data', {}).get('monthly_performance', {}).get('months', [])
        self.assertEqual(len(monthly), 6)


if __name__ == '__main__':
    unittest.main()
