import unittest

from flask import Flask

from models import User, Workspace, db
import models_crm  # noqa: F401
from models_crm import APIKey, OAuthAccessToken, OAuthClient
from routes.public_api import bp as public_api_bp
from services.api_auth_service import APIAuthService


class TestPhase21PublicAPISecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        cls.app.secret_key = 'phase21-public-api-security'
        db.init_app(cls.app)
        cls.app.register_blueprint(public_api_bp)

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        ws1 = Workspace(company_name='Phase21 Workspace 1')
        ws2 = Workspace(company_name='Phase21 Workspace 2')
        db.session.add_all([ws1, ws2])
        db.session.flush()

        user1 = User(
            workspace_id=ws1.id,
            name='Phase21 User 1',
            email='phase21-user1@example.com',
            password_hash='hash',
            role='admin',
        )
        user2 = User(
            workspace_id=ws2.id,
            name='Phase21 User 2',
            email='phase21-user2@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add_all([user1, user2])
        db.session.commit()

        self.ws1_id = ws1.id
        self.ws2_id = ws2.id
        self.user1_id = user1.id
        self.user2_id = user2.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self, client, workspace_id, user_id):
        with client.session_transaction() as sess:
            sess['workspace_id'] = workspace_id
            sess['user_id'] = user_id

    def _issue_oauth_token(self, workspace_id, user_id):
        client, client_secret = APIAuthService.create_oauth_client(
            workspace_id=workspace_id,
            name='Phase21 Client',
            redirect_uris=['https://example.com/callback'],
            created_by=user_id,
            scopes='read,write',
        )
        auth_code = APIAuthService.issue_authorization_code(
            client=client,
            workspace_id=workspace_id,
            user_id=user_id,
            redirect_uri='https://example.com/callback',
            scopes='read,write',
        )
        token_payload = APIAuthService.exchange_authorization_code(
            client=client,
            raw_code=auth_code,
            redirect_uri='https://example.com/callback',
        )
        return client, client_secret, token_payload['access_token']

    def test_revoke_api_key_deactivates_key_and_blocks_public_access(self):
        api_key_row, plaintext_key = APIAuthService.generate_api_key(
            workspace_id=self.ws1_id,
            name='Phase21 Key',
            created_by=self.user1_id,
            scopes='read',
        )

        with self.app.test_client() as client:
            pre = client.get('/public/api/v1/contacts', headers={'X-API-Key': plaintext_key})
            self.assertEqual(pre.status_code, 200)

            self._login(client, self.ws1_id, self.user1_id)
            revoke = client.delete(f'/api/v1/public-auth/api-keys/{api_key_row.id}')
            self.assertEqual(revoke.status_code, 200)
            self.assertEqual(revoke.get_json().get('status'), 'revoked')

            post = client.get('/public/api/v1/contacts', headers={'X-API-Key': plaintext_key})
            self.assertEqual(post.status_code, 401)

        refreshed = db.session.get(APIKey, api_key_row.id)
        self.assertFalse(refreshed.is_active)

    def test_revoke_api_key_is_workspace_scoped(self):
        api_key_row, _ = APIAuthService.generate_api_key(
            workspace_id=self.ws2_id,
            name='Phase21 Key WS2',
            created_by=self.user2_id,
            scopes='read',
        )

        with self.app.test_client() as client:
            self._login(client, self.ws1_id, self.user1_id)
            response = client.delete(f'/api/v1/public-auth/api-keys/{api_key_row.id}')

        self.assertEqual(response.status_code, 404)
        self.assertTrue(db.session.get(APIKey, api_key_row.id).is_active)

    def test_deactivate_oauth_client_revokes_existing_tokens(self):
        oauth_client, _, access_token = self._issue_oauth_token(self.ws1_id, self.user1_id)

        with self.app.test_client() as client:
            pre = client.get('/public/api/v1/contacts', headers={'Authorization': f'Bearer {access_token}'})
            self.assertEqual(pre.status_code, 200)

            self._login(client, self.ws1_id, self.user1_id)
            deactivate = client.delete(f'/api/v1/public-auth/oauth-clients/{oauth_client.id}')

            self.assertEqual(deactivate.status_code, 200)
            payload = deactivate.get_json()
            self.assertEqual(payload.get('status'), 'deactivated')
            self.assertGreaterEqual(payload.get('revoked_tokens', 0), 1)

            post = client.get('/public/api/v1/contacts', headers={'Authorization': f'Bearer {access_token}'})
            self.assertEqual(post.status_code, 401)

        refreshed_client = db.session.get(OAuthClient, oauth_client.id)
        self.assertFalse(refreshed_client.is_active)
        token_hash = APIAuthService._hash_secret(access_token)
        token_row = OAuthAccessToken.query.filter_by(token_hash=token_hash).first()
        self.assertIsNotNone(token_row.revoked_at)

    def test_oauth_revoke_endpoint_revokes_access_token(self):
        oauth_client, client_secret, access_token = self._issue_oauth_token(self.ws1_id, self.user1_id)

        with self.app.test_client() as client:
            pre = client.get('/public/api/v1/contacts', headers={'Authorization': f'Bearer {access_token}'})
            self.assertEqual(pre.status_code, 200)

            revoke = client.post('/public/oauth/revoke', data={
                'token': access_token,
                'client_id': oauth_client.client_id,
                'client_secret': client_secret,
            })

            self.assertEqual(revoke.status_code, 200)
            self.assertEqual(revoke.get_json().get('status'), 'revoked')

            post = client.get('/public/api/v1/contacts', headers={'Authorization': f'Bearer {access_token}'})
            self.assertEqual(post.status_code, 401)

    def test_oauth_revoke_rejects_invalid_client_credentials(self):
        oauth_client, _, access_token = self._issue_oauth_token(self.ws1_id, self.user1_id)

        with self.app.test_client() as client:
            response = client.post('/public/oauth/revoke', data={
                'token': access_token,
                'client_id': oauth_client.client_id,
                'client_secret': 'wrong-secret',
            })

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json().get('error'), 'invalid_client')


if __name__ == '__main__':
    unittest.main()