import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from models import User, Workspace, db
import models_crm  # noqa: F401
from models_crm import Company, Deal, DealStage, Pipeline
from routes.pipeline import bp as pipeline_bp
from services.pipeline_advanced_service import PipelineAdvancedService


class _FakeIdQuery:
    def __init__(self, ids):
        self._rows = [(deal_id,) for deal_id in ids]

    def with_entities(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._rows)


class TestPhase27PipelineAdvancedServiceGuards(unittest.TestCase):
    def test_find_duplicates_empty_scope_returns_empty(self):
        result = PipelineAdvancedService.find_deal_duplicates(workspace_id=1, accessible_deal_ids=[])
        self.assertEqual(result, [])

    def test_merge_deals_scope_guard_rejects_out_of_scope_ids(self):
        with self.assertRaises(PermissionError) as exc:
            PipelineAdvancedService.merge_deals(
                workspace_id=1,
                primary_id=10,
                secondary_id=11,
                user_id=99,
                accessible_deal_ids={10},
            )

        self.assertEqual(str(exc.exception), 'Access denied to one or more deals')


class TestPhase27PipelineRouteSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        cls.app.secret_key = 'phase27-pipeline-security'
        db.init_app(cls.app)
        cls.app.register_blueprint(pipeline_bp)

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        ws = Workspace(company_name='Phase27 Workspace')
        db.session.add(ws)
        db.session.flush()

        user = User(
            workspace_id=ws.id,
            name='Phase27 User',
            email='phase27-user@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add(user)
        db.session.flush()

        company = Company(workspace_id=ws.id, name='Phase27 Company')
        db.session.add(company)
        db.session.flush()

        pipeline = Pipeline(workspace_id=ws.id, name='Phase27 Pipeline', is_default=True)
        db.session.add(pipeline)
        db.session.flush()

        stage = DealStage(pipeline_id=pipeline.id, name='Discovery', order=1, probability=50)
        db.session.add(stage)
        db.session.flush()

        deal_primary = Deal(
            workspace_id=ws.id,
            name='Phase27 Primary Deal',
            company_id=company.id,
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            owner_id=user.id,
            value=1000,
        )
        deal_secondary = Deal(
            workspace_id=ws.id,
            name='Phase27 Secondary Deal',
            company_id=company.id,
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            owner_id=user.id,
            value=500,
        )
        db.session.add_all([deal_primary, deal_secondary])
        db.session.commit()

        self.workspace_id = ws.id
        self.user_id = user.id
        self.primary_id = deal_primary.id
        self.secondary_id = deal_secondary.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _client_with_session(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['workspace_id'] = self.workspace_id
            sess['user_role'] = 'admin'
        return client

    def test_duplicates_returns_empty_when_no_access_scope(self):
        fake_user = SimpleNamespace(id=self.user_id, workspace_id=self.workspace_id)

        with patch('utils.permissions.get_current_user_from_session', return_value=fake_user), patch(
            'utils.permissions.get_accessible_entities_query', return_value=_FakeIdQuery([])
        ), patch('routes.pipeline.PipelineAdvancedService.find_deal_duplicates') as mock_find:
            response = self._client_with_session().get('/api/v1/deals/duplicates')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get('duplicate_groups'), [])
        mock_find.assert_not_called()

    def test_duplicates_passes_access_scope_to_service(self):
        fake_user = SimpleNamespace(id=self.user_id, workspace_id=self.workspace_id)

        with patch('utils.permissions.get_current_user_from_session', return_value=fake_user), patch(
            'utils.permissions.get_accessible_entities_query',
            return_value=_FakeIdQuery([self.primary_id]),
        ), patch(
            'routes.pipeline.PipelineAdvancedService.find_deal_duplicates', return_value=[]
        ) as mock_find:
            response = self._client_with_session().get('/api/v1/deals/duplicates')

        self.assertEqual(response.status_code, 200)
        mock_find.assert_called_once_with(
            self.workspace_id,
            accessible_deal_ids={self.primary_id},
        )

    def test_merge_deals_requires_write_access_on_both_records(self):
        fake_user = SimpleNamespace(id=self.user_id, workspace_id=self.workspace_id)

        with patch('utils.permissions.get_current_user_from_session', return_value=fake_user), patch(
            'utils.permissions.check_entity_access', side_effect=[True, False]
        ), patch('routes.pipeline.PipelineAdvancedService.merge_deals') as mock_merge:
            response = self._client_with_session().post(
                '/api/v1/deals/merge',
                json={'primary_id': self.primary_id, 'secondary_id': self.secondary_id},
            )

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Access denied to one or more deals')
        mock_merge.assert_not_called()


if __name__ == '__main__':
    unittest.main()
