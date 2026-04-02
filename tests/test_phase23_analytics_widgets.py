import json
import unittest

from flask import Flask

from models import User, Workspace, db
import models_crm  # noqa: F401
from models_crm import DashboardWidget
from routes.analytics import bp as analytics_bp


class TestPhase23AnalyticsWidgets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        cls.app.secret_key = 'phase23-analytics-widgets'
        db.init_app(cls.app)
        cls.app.register_blueprint(analytics_bp)

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        ws = Workspace(company_name='Phase23 Workspace')
        db.session.add(ws)
        db.session.flush()

        user = User(
            workspace_id=ws.id,
            name='Phase23 User',
            email='phase23-user@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add(user)
        db.session.flush()

        self.workspace_id = ws.id
        self.user_id = user.id

        widget_types = [
            'kpi_card',
            'bar_chart',
            'funnel',
            'pie_chart',
            'leaderboard',
            'activity_feed',
            'goal_progress',
            'heatmap',
        ]

        self.widget_ids = {}
        for widget_type in widget_types:
            widget = DashboardWidget(
                workspace_id=self.workspace_id,
                user_id=self.user_id,
                widget_type=widget_type,
                title=f'Phase23 {widget_type}',
                config_json=json.dumps({'limit': 5, 'period': 'month'}),
            )
            db.session.add(widget)
            db.session.flush()
            self.widget_ids[widget_type] = widget.id

        unknown = DashboardWidget(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            widget_type='unknown_type',
            title='Unknown',
            config_json='{}',
        )
        db.session.add(unknown)
        db.session.flush()
        self.unknown_widget_id = unknown.id

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self, client):
        with client.session_transaction() as sess:
            sess['workspace_id'] = self.workspace_id
            sess['user_id'] = self.user_id

    def test_widget_data_endpoint_supports_all_known_widget_types(self):
        with self.app.test_client() as client:
            self._login(client)
            for widget_type, widget_id in self.widget_ids.items():
                response = client.get(f'/api/v1/analytics/widget-data/{widget_id}')
                self.assertEqual(
                    response.status_code,
                    200,
                    msg=f'Expected 200 for {widget_type}, got {response.status_code}',
                )
                payload = response.get_json()
                self.assertTrue(payload.get('success'))
                self.assertEqual(payload.get('widget_id'), widget_id)
                self.assertEqual(payload.get('widget_type'), widget_type)
                self.assertIn('data', payload)

    def test_widget_data_endpoint_rejects_unknown_widget_type(self):
        with self.app.test_client() as client:
            self._login(client)
            response = client.get(f'/api/v1/analytics/widget-data/{self.unknown_widget_id}')

        self.assertEqual(response.status_code, 400)
        self.assertIn('Unknown widget type', response.get_json().get('error', ''))


if __name__ == '__main__':
    unittest.main()
