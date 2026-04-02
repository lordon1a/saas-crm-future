import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from routes.integrations import integrations_bp


class TestPhase22IntegrationsAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.secret_key = 'integrations-audit-phase22'
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

    def test_facebook_callback_success_writes_audit_event(self):
        with self._auth_patch(), patch(
            'routes.integrations.FacebookLeadAdsService.handle_oauth_callback',
            return_value=SimpleNamespace(id=321),
        ), patch('routes.integrations.AuditService.log_event') as audit_mock:
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77
                    sess['facebook_oauth_state'] = '77:99:nonce'

                response = client.get('/api/v1/integrations/facebook/callback?code=abc&state=77:99:nonce')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(audit_mock.called)
        kwargs = audit_mock.call_args.kwargs
        self.assertEqual(kwargs.get('workspace_id'), 77)
        self.assertEqual(kwargs.get('user_id'), 99)
        self.assertEqual(kwargs.get('action'), 'integration.oauth_connected')
        self.assertEqual(kwargs.get('entity_type'), 'integration')
        self.assertEqual(kwargs.get('entity_id'), 'facebook')

    def test_google_ads_invalid_state_writes_failed_audit_event(self):
        with self._auth_patch(), patch('routes.integrations.AuditService.log_event') as audit_mock:
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77
                    sess['google_ads_oauth_state'] = '77:99:expected'

                response = client.get('/api/v1/integrations/google-ads/callback?code=abc&state=77:99:other')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(audit_mock.called)
        kwargs = audit_mock.call_args.kwargs
        self.assertEqual(kwargs.get('workspace_id'), 77)
        self.assertEqual(kwargs.get('user_id'), 99)
        self.assertEqual(kwargs.get('action'), 'integration.oauth_failed')
        self.assertEqual(kwargs.get('entity_id'), 'google_ads')
        self.assertEqual((kwargs.get('metadata') or {}).get('failure_reason'), 'invalid_state')

    def test_facebook_webhook_rejection_writes_workspace_scoped_audit_event(self):
        with patch(
            'routes.integrations.FacebookLeadAdsService.process_lead_webhook',
            return_value={'ok': False, 'reason': 'email missing in payload', 'workspace_id': 77},
        ), patch('routes.integrations.AuditService.log_event') as audit_mock:
            with self.app.test_client() as client:
                response = client.post('/api/v1/webhooks/facebook/lead', json={'entry': []})

        self.assertEqual(response.status_code, 400)
        self.assertTrue(audit_mock.called)
        kwargs = audit_mock.call_args.kwargs
        self.assertEqual(kwargs.get('workspace_id'), 77)
        self.assertIsNone(kwargs.get('user_id'))
        self.assertEqual(kwargs.get('action'), 'integration.webhook_rejected')
        self.assertEqual(kwargs.get('entity_id'), 'facebook')

    def test_google_ads_disconnect_writes_audit_event(self):
        with self._auth_patch(), patch(
            'routes.integrations.GoogleAdsService.disconnect',
            return_value=True,
        ), patch('routes.integrations.AuditService.log_event') as audit_mock:
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['user_id'] = 99
                    sess['workspace_id'] = 77

                response = client.delete('/api/v1/integrations/google-ads')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(audit_mock.called)
        kwargs = audit_mock.call_args.kwargs
        self.assertEqual(kwargs.get('workspace_id'), 77)
        self.assertEqual(kwargs.get('user_id'), 99)
        self.assertEqual(kwargs.get('action'), 'integration.disconnected')
        self.assertEqual(kwargs.get('entity_id'), 'google_ads')
        self.assertTrue((kwargs.get('metadata') or {}).get('success'))


if __name__ == '__main__':
    unittest.main()
