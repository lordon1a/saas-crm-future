"""
Phase 6 property-style validation checks.
Covers:
- Property 30: API key authentication
- Property 31: Rate limiting enforcement
- Property 32/33/34: Webhook dispatch, retry logic, signature verification
"""

import hmac
import json
import threading
from datetime import datetime
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer

from app import app
from config import Config
from models import User
from models_crm import Company


class CaptureHandler(BaseHTTPRequestHandler):
    captured = []

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0') or 0)
        body = self.rfile.read(length).decode('utf-8') if length else ''
        CaptureHandler.captured.append({
            'path': self.path,
            'headers': dict(self.headers),
            'body': body,
        })
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, format, *args):
        return


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    with app.app_context():
        user = User.query.filter_by(email='admin@example.com').first() or User.query.first()
        company = Company.query.filter_by(workspace_id=user.workspace_id).first()

    client = app.test_client()

    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['workspace_id'] = user.workspace_id
        sess['user_role'] = user.role

    origin = {'Origin': 'http://localhost'}

    # ------------------------------------------------------------------
    # Property 30: API key authentication
    # ------------------------------------------------------------------
    key_resp = client.post('/api/v1/public-auth/api-keys', json={'name': 'prop-30-key'}, headers=origin)
    assert_true(key_resp.status_code == 201, 'API key should be created')
    api_key = key_resp.get_json()['api_key']

    ok_resp = client.get('/public/api/v1/contacts?limit=1', headers={'X-API-Key': api_key})
    assert_true(ok_resp.status_code == 200, 'Valid API key should authorize request')

    fail_resp = client.get('/public/api/v1/contacts?limit=1', headers={'X-API-Key': 'invalid-key'})
    assert_true(fail_resp.status_code == 401, 'Invalid API key should be rejected')

    # ------------------------------------------------------------------
    # Property 31: Rate limiting enforcement
    # ------------------------------------------------------------------
    Config.PUBLIC_API_RATE_LIMIT_PER_HOUR = 2
    Config.PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS = 3600

    rl_key_resp = client.post('/api/v1/public-auth/api-keys', json={'name': 'prop-31-key'}, headers=origin)
    assert_true(rl_key_resp.status_code == 201, 'Rate limit test API key should be created')
    rl_key = rl_key_resp.get_json()['api_key']

    rl_headers = {'X-API-Key': rl_key}
    r1 = client.get('/public/api/v1/companies?limit=1', headers=rl_headers)
    r2 = client.get('/public/api/v1/companies?limit=1', headers=rl_headers)
    r3 = client.get('/public/api/v1/companies?limit=1', headers=rl_headers)

    assert_true(r1.status_code == 200 and r2.status_code == 200, 'Requests under limit should succeed')
    assert_true(r3.status_code == 429, 'Request above limit should return 429')
    assert_true(bool(r3.headers.get('Retry-After')), '429 should include Retry-After header')

    # ------------------------------------------------------------------
    # Property 32 + 34: Webhook dispatch + signature verification
    # ------------------------------------------------------------------
    CaptureHandler.captured = []
    server = HTTPServer(('127.0.0.1', 0), CaptureHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    wh_ok = client.post('/api/v1/public-auth/webhooks', json={
        'name': 'prop-webhook-success',
        'target_url': f'http://127.0.0.1:{port}/receiver',
        'event_types': ['contact.created']
    }, headers=origin)
    assert_true(wh_ok.status_code == 201, 'Success webhook subscription should be created')
    wh_ok_body = wh_ok.get_json()
    wh_secret = wh_ok_body['secret']

    email = f"phase6-prop-{int(datetime.utcnow().timestamp())}@example.com"
    contact_resp = client.post('/api/v1/contacts', json={
        'first_name': 'Phase6',
        'last_name': 'Property',
        'email': email,
        'company_id': company.id if company else None,
    }, headers=origin)
    assert_true(contact_resp.status_code == 201, 'Contact should be created and trigger webhook')

    server.shutdown()
    assert_true(len(CaptureHandler.captured) >= 1, 'At least one webhook delivery should be captured')

    captured = CaptureHandler.captured[0]
    signature_header = captured['headers'].get(Config.WEBHOOK_SIGNATURE_HEADER)
    assert_true(bool(signature_header), 'Webhook delivery should include signature header')

    expected_signature = 'sha256=' + hmac.new(
        wh_secret.encode('utf-8'),
        captured['body'].encode('utf-8'),
        sha256
    ).hexdigest()
    assert_true(signature_header == expected_signature, 'Webhook signature should match payload HMAC')

    payload = json.loads(captured['body'])
    assert_true(payload.get('event') == 'contact.created', 'Webhook payload event should match dispatched event')

    # ------------------------------------------------------------------
    # Property 33: Webhook retry logic
    # ------------------------------------------------------------------
    Config.WEBHOOK_RETRY_ATTEMPTS = 3
    Config.WEBHOOK_RETRY_BASE_SECONDS = 1

    wh_fail = client.post('/api/v1/public-auth/webhooks', json={
        'name': 'prop-webhook-fail',
        'target_url': 'http://127.0.0.1:1/unreachable',
        'event_types': ['deal.updated']
    }, headers=origin)
    assert_true(wh_fail.status_code == 201, 'Fail webhook subscription should be created')
    wh_fail_id = wh_fail.get_json()['id']

    test_fail = client.post(f'/api/v1/public-auth/webhooks/{wh_fail_id}/test', headers=origin)
    assert_true(test_fail.status_code == 200, 'Webhook test endpoint should return delivery payload')
    fail_payload = test_fail.get_json()

    assert_true(fail_payload.get('status') == 'failed', 'Unreachable target should end in failed delivery status')
    assert_true(fail_payload.get('attempt_count') == 3, 'Failed delivery should retry 3 attempts')

    print('Property 30 passed: API key authentication')
    print('Property 31 passed: Rate limiting enforcement')
    print('Property 32 passed: Webhook event dispatch')
    print('Property 33 passed: Webhook retry logic')
    print('Property 34 passed: Webhook signature verification')


if __name__ == '__main__':
    run()
