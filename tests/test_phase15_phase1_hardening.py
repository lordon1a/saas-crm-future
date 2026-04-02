import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from routes.import_wizard import (
    import_bp,
    _create_import_job,
    _update_import_job,
    clear_import_jobs,
)
from routes.integrations import integrations_bp


class TestPhase15ImportWizardStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'import-status-secret'
        cls.app.register_blueprint(import_bp)

    def setUp(self):
        clear_import_jobs()

    def tearDown(self):
        clear_import_jobs()

    def test_status_requires_authentication(self):
        with self.app.test_client() as client:
            response = client.get('/api/v1/import/status/job_1')

        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Authentication required')

    def test_status_returns_404_for_unknown_job(self):
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 99
                sess['workspace_id'] = 77

            response = client.get('/api/v1/import/status/job_unknown')

        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertEqual(payload.get('error'), 'Import job not found')

    def test_status_returns_saved_job_for_same_workspace(self):
        _create_import_job('job_abc', 77, 'contacts', 'contacts.csv')
        _update_import_job(
            'job_abc',
            status='completed',
            progress=100,
            message='Import completed',
            imported_rows=12,
            updated_rows=2,
            skipped_rows=1,
            failed_rows=0,
            total_rows=15,
        )

        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 99
                sess['workspace_id'] = 77

            response = client.get('/api/v1/import/status/job_abc')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get('job_id'), 'job_abc')
        self.assertEqual(payload.get('status'), 'completed')
        self.assertEqual(payload.get('progress'), 100)
        self.assertEqual(payload.get('imported_rows'), 12)

    def test_status_is_workspace_scoped(self):
        _create_import_job('job_private', 77, 'contacts', 'contacts.csv')
        _update_import_job('job_private', status='completed', progress=100)

        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 99
                sess['workspace_id'] = 88

            response = client.get('/api/v1/import/status/job_private')

        self.assertEqual(response.status_code, 404)


class TestPhase15IntegrationsOAuthRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'integrations-phase1-secret'
        cls.app.config['FACEBOOK_APP_ID'] = 'fb-client-id'
        cls.app.config['FACEBOOK_REDIRECT_URI'] = 'http://localhost/api/v1/integrations/facebook/callback'
        cls.app.config['GOOGLE_ADS_CLIENT_ID'] = 'gads-client-id'
        cls.app.config['GOOGLE_ADS_REDIRECT_URI'] = 'http://localhost/api/v1/integrations/google-ads/callback'
        cls.app.register_blueprint(integrations_bp)

    @staticmethod
    def _auth_patch():
        return patch(
            'routes.integrations.User',
            SimpleNamespace(query=SimpleNamespace(get=lambda _user_id: SimpleNamespace(id=_user_id))),
        )

    def test_facebook_auth_url_sets_session_state(self):
        with self._auth_patch():
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.get('/api/v1/integrations/facebook/auth')

                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertIn('auth_url', payload)

                with client.session_transaction() as sess:
                    state = sess.get('facebook_oauth_state')
                    self.assertTrue(state)
                    self.assertTrue(state.startswith('77:99:'))

    def test_facebook_callback_rejects_invalid_state(self):
        with self._auth_patch():
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77
                    sess['facebook_oauth_state'] = '77:99:expected'

                response = client.get('/api/v1/integrations/facebook/callback?code=abc&state=77:99:other')

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIn('Invalid OAuth state', payload.get('error', ''))

    def test_facebook_callback_success(self):
        with self._auth_patch(), patch(
            'routes.integrations.FacebookLeadAdsService.handle_oauth_callback',
            return_value=SimpleNamespace(id=321),
        ):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77
                    sess['facebook_oauth_state'] = '77:99:nonce'

                response = client.get('/api/v1/integrations/facebook/callback?code=abc&state=77:99:nonce')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get('success'))
        self.assertEqual(payload.get('integration_id'), 321)

    def test_google_ads_auth_url_sets_session_state(self):
        with self._auth_patch():
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.get('/api/v1/integrations/google-ads/auth')

                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertIn('auth_url', payload)

                with client.session_transaction() as sess:
                    state = sess.get('google_ads_oauth_state')
                    self.assertTrue(state)
                    self.assertTrue(state.startswith('77:99:'))

    def test_google_ads_callback_rejects_workspace_mismatch(self):
        with self._auth_patch():
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77
                    sess['google_ads_oauth_state'] = '55:99:nonce'

                response = client.get('/api/v1/integrations/google-ads/callback?code=abc&state=55:99:nonce')

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertIn('does not match active session', payload.get('error', ''))

    def test_google_ads_callback_success(self):
        with self._auth_patch(), patch(
            'routes.integrations.GoogleAdsService.handle_oauth_callback',
            return_value=SimpleNamespace(id=654),
        ):
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77
                    sess['google_ads_oauth_state'] = '77:99:nonce'

                response = client.get('/api/v1/integrations/google-ads/callback?code=abc&state=77:99:nonce')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get('success'))
        self.assertEqual(payload.get('integration_id'), 654)


if __name__ == '__main__':
    unittest.main()
