import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from models import User, Workspace, db
import models_crm  # noqa: F401
from models_crm import Contact, EmailSequenceEnrollment
from routes.email_hub import email_hub_bp
from services.email_hub_service import EmailHubService


class TestPhase18EmailEnrollmentRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'phase18-email-routes'
        cls.app.register_blueprint(email_hub_bp)

    def test_enroll_requires_write_access(self):
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 99
                sess['workspace_id'] = 77
                sess['user_role'] = 'read-only'

            response = client.post('/api/v1/email/sequences/12/enroll', json={'contact_id': 5})

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Write permission required')

    def test_unenroll_requires_write_access(self):
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 99
                sess['workspace_id'] = 77
                sess['user_role'] = 'readonly'

            response = client.delete('/api/v1/email/enrollments/12', json={'reason': 'manual'})

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Write permission required')

    def test_unenroll_passes_workspace_scope_to_service(self):
        with patch(
            'routes.email_hub.EmailHubService.unenroll_contact',
            return_value=SimpleNamespace(id=12),
        ) as unenroll_mock:
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77
                    sess['user_role'] = 'admin'

                response = client.delete('/api/v1/email/enrollments/12', json={'reason': 'manual'})

        self.assertEqual(response.status_code, 200)
        unenroll_mock.assert_called_once_with(
            enrollment_id=12,
            reason='manual',
            workspace_id=77,
        )

    def test_unenroll_maps_not_found_to_404(self):
        with patch(
            'routes.email_hub.EmailHubService.unenroll_contact',
            side_effect=ValueError('Enrollment not found'),
        ):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77
                    sess['user_role'] = 'admin'

                response = client.delete('/api/v1/email/enrollments/999', json={'reason': 'manual'})

        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Enrollment not found')

    def test_enroll_maps_contact_not_found_to_404(self):
        with patch(
            'routes.email_hub.EmailHubService.enroll_contact',
            side_effect=ValueError('Contact not found'),
        ):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77
                    sess['user_role'] = 'admin'

                response = client.post('/api/v1/email/sequences/12/enroll', json={'contact_id': 5})

        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Contact not found')


class TestPhase18EmailEnrollmentService(unittest.TestCase):
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

        ws1 = Workspace(company_name='Phase18 Workspace 1')
        ws2 = Workspace(company_name='Phase18 Workspace 2')
        db.session.add_all([ws1, ws2])
        db.session.flush()

        user1 = User(
            workspace_id=ws1.id,
            name='Phase18 Admin 1',
            email='phase18-admin1@example.com',
            password_hash='hash',
            role='admin',
        )
        user2 = User(
            workspace_id=ws2.id,
            name='Phase18 Admin 2',
            email='phase18-admin2@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add_all([user1, user2])
        db.session.flush()

        contact1 = Contact(
            workspace_id=ws1.id,
            first_name='Ada',
            last_name='Lovelace',
            email='ada.phase18@example.com',
        )
        contact2 = Contact(
            workspace_id=ws2.id,
            first_name='Grace',
            last_name='Hopper',
            email='grace.phase18@example.com',
        )
        contact_no_email = Contact(
            workspace_id=ws1.id,
            first_name='No',
            last_name='Email',
            email=None,
        )
        db.session.add_all([contact1, contact2, contact_no_email])
        db.session.flush()

        sequence = EmailHubService.create_sequence(
            workspace_id=ws1.id,
            user_id=user1.id,
            name='Phase18 Sequence',
            description='phase18-test',
            steps=[
                {
                    'step_order': 1,
                    'delay_hours': 0,
                    'subject_override': 'Hello',
                    'body_override': 'World',
                }
            ],
        )

        self.ws1_id = ws1.id
        self.ws2_id = ws2.id
        self.user1_id = user1.id
        self.sequence_id = sequence.id
        self.contact1_id = contact1.id
        self.contact2_id = contact2.id
        self.contact_no_email_id = contact_no_email.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_enroll_rejects_contact_from_different_workspace(self):
        with self.assertRaises(ValueError) as exc:
            EmailHubService.enroll_contact(
                workspace_id=self.ws1_id,
                sequence_id=self.sequence_id,
                contact_id=self.contact2_id,
                enrolled_by=self.user1_id,
            )

        self.assertEqual(str(exc.exception), 'Contact not found')

    def test_enroll_rejects_contact_without_email(self):
        with self.assertRaises(ValueError) as exc:
            EmailHubService.enroll_contact(
                workspace_id=self.ws1_id,
                sequence_id=self.sequence_id,
                contact_id=self.contact_no_email_id,
                enrolled_by=self.user1_id,
            )

        self.assertEqual(str(exc.exception), 'Contact does not have an email address')

    def test_unenroll_rejects_workspace_mismatch(self):
        enrollment = EmailHubService.enroll_contact(
            workspace_id=self.ws1_id,
            sequence_id=self.sequence_id,
            contact_id=self.contact1_id,
            enrolled_by=self.user1_id,
        )

        with self.assertRaises(ValueError) as exc:
            EmailHubService.unenroll_contact(
                enrollment_id=enrollment.id,
                reason='manual',
                workspace_id=self.ws2_id,
            )

        self.assertEqual(str(exc.exception), 'Enrollment not found')

        fresh = EmailSequenceEnrollment.query.get(enrollment.id)
        self.assertIsNotNone(fresh)
        self.assertEqual(fresh.status, 'active')


if __name__ == '__main__':
    unittest.main()