import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from models import User, Workspace, db
import models_crm  # noqa: F401
from models_crm import Company, Contact, Deal, DealStage, Milestone, Pipeline
from routes.tasks import tasks_bp
from services.task_service import TaskService


def _fake_user_model(user):
    return SimpleNamespace(query=SimpleNamespace(get=lambda _user_id: user))


class TestPhase19TaskServiceSecurity(unittest.TestCase):
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

        ws1 = Workspace(company_name='Phase19 Workspace 1')
        ws2 = Workspace(company_name='Phase19 Workspace 2')
        db.session.add_all([ws1, ws2])
        db.session.flush()

        user1 = User(
            workspace_id=ws1.id,
            name='Phase19 User 1',
            email='phase19-user1@example.com',
            password_hash='hash',
            role='admin',
        )
        user2 = User(
            workspace_id=ws2.id,
            name='Phase19 User 2',
            email='phase19-user2@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add_all([user1, user2])
        db.session.flush()

        company1 = Company(workspace_id=ws1.id, name='Phase19 Company 1')
        company1_alt = Company(workspace_id=ws1.id, name='Phase19 Company 1 Alt')
        company2 = Company(workspace_id=ws2.id, name='Phase19 Company 2')
        db.session.add_all([company1, company1_alt, company2])
        db.session.flush()

        contact1 = Contact(
            workspace_id=ws1.id,
            company_id=company1.id,
            first_name='Ada',
            last_name='Lovelace',
            email='ada.phase19@example.com',
        )
        contact2 = Contact(
            workspace_id=ws2.id,
            company_id=company2.id,
            first_name='Grace',
            last_name='Hopper',
            email='grace.phase19@example.com',
        )
        db.session.add_all([contact1, contact2])
        db.session.flush()

        milestone1 = Milestone(
            workspace_id=ws1.id,
            name='Phase19 Milestone 1',
            company_id=company1.id,
            status='active',
        )
        milestone2 = Milestone(
            workspace_id=ws2.id,
            name='Phase19 Milestone 2',
            company_id=company2.id,
            status='active',
        )
        db.session.add_all([milestone1, milestone2])
        db.session.flush()

        pipeline1 = Pipeline(workspace_id=ws1.id, name='Phase19 Pipeline', is_default=True)
        db.session.add(pipeline1)
        db.session.flush()

        stage1 = DealStage(pipeline_id=pipeline1.id, name='Qualified', order=1, probability=50)
        db.session.add(stage1)
        db.session.flush()

        deal1 = Deal(
            workspace_id=ws1.id,
            name='Phase19 Deal',
            company_id=company1.id,
            contact_id=contact1.id,
            pipeline_id=pipeline1.id,
            stage_id=stage1.id,
            owner_id=user1.id,
            value=1000,
        )
        db.session.add(deal1)
        db.session.commit()

        self.ws1_id = ws1.id
        self.ws2_id = ws2.id
        self.user1_id = user1.id
        self.user2_id = user2.id
        self.company1_id = company1.id
        self.company1_alt_id = company1_alt.id
        self.company2_id = company2.id
        self.contact1_id = contact1.id
        self.contact2_id = contact2.id
        self.milestone1_id = milestone1.id
        self.milestone2_id = milestone2.id
        self.deal1_id = deal1.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_create_task_rejects_cross_workspace_assignee(self):
        with self.assertRaises(ValueError) as exc:
            TaskService.create_task(
                workspace_id=self.ws1_id,
                title='Phase19 Task',
                assignee_id=self.user2_id,
            )

        self.assertEqual(str(exc.exception), 'Assignee not found')

    def test_create_task_rejects_cross_workspace_company(self):
        with self.assertRaises(ValueError) as exc:
            TaskService.create_task(
                workspace_id=self.ws1_id,
                title='Phase19 Task',
                company_id=self.company2_id,
            )

        self.assertEqual(str(exc.exception), 'Company not found')

    def test_update_task_rejects_cross_workspace_contact(self):
        task = TaskService.create_task(
            workspace_id=self.ws1_id,
            title='Phase19 Task',
            assignee_id=self.user1_id,
            company_id=self.company1_id,
            deal_id=self.deal1_id,
            milestone_id=self.milestone1_id,
            contact_id=self.contact1_id,
        )

        with self.assertRaises(ValueError) as exc:
            TaskService.update_task(
                task_id=task.id,
                workspace_id=self.ws1_id,
                contact_id=self.contact2_id,
            )

        self.assertEqual(str(exc.exception), 'Contact not found')

    def test_update_task_rejects_company_deal_mismatch(self):
        task = TaskService.create_task(
            workspace_id=self.ws1_id,
            title='Phase19 Task',
            assignee_id=self.user1_id,
            company_id=self.company1_id,
            deal_id=self.deal1_id,
            milestone_id=self.milestone1_id,
            contact_id=self.contact1_id,
        )

        with self.assertRaises(ValueError) as exc:
            TaskService.update_task(
                task_id=task.id,
                workspace_id=self.ws1_id,
                company_id=self.company1_alt_id,
            )

        self.assertEqual(str(exc.exception), 'Deal does not belong to selected company')

    def test_create_milestone_rejects_cross_workspace_company(self):
        with self.assertRaises(ValueError) as exc:
            TaskService.create_milestone(
                workspace_id=self.ws1_id,
                name='Phase19 New Milestone',
                company_id=self.company2_id,
            )

        self.assertEqual(str(exc.exception), 'Company not found')

    def test_update_milestone_rejects_cross_workspace_company(self):
        with self.assertRaises(ValueError) as exc:
            TaskService.update_milestone(
                milestone_id=self.milestone1_id,
                workspace_id=self.ws1_id,
                company_id=self.company2_id,
            )

        self.assertEqual(str(exc.exception), 'Company not found')


class TestPhase19TaskRouteWriteAccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'phase19-task-routes'
        cls.app.register_blueprint(tasks_bp)

    def test_create_task_requires_write_access(self):
        fake_user = SimpleNamespace(id=501, workspace_id=77)

        with patch('routes.tasks.User', _fake_user_model(fake_user)):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 501
                    sess['workspace_id'] = 77
                    sess['user_role'] = 'viewer'

                response = client.post('/api/v1/tasks', json={'title': 'Blocked task'})

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Write permission required')

    def test_complete_task_requires_write_access(self):
        fake_user = SimpleNamespace(id=502, workspace_id=77)

        with patch('routes.tasks.User', _fake_user_model(fake_user)):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 502
                    sess['workspace_id'] = 77
                    sess['user_role'] = 'readonly'

                response = client.post('/api/v1/tasks/1/complete')

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Write permission required')

    def test_create_milestone_requires_write_access(self):
        fake_user = SimpleNamespace(id=503, workspace_id=77)

        with patch('routes.tasks.User', _fake_user_model(fake_user)):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 503
                    sess['workspace_id'] = 77
                    sess['user_role'] = 'read-only'

                response = client.post('/api/v1/milestones', json={'name': 'Blocked milestone'})

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Write permission required')


if __name__ == '__main__':
    unittest.main()
