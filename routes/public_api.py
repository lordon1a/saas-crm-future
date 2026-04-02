from urllib.parse import urlencode

from flask import Blueprint, g, jsonify, redirect, request, session

from models import User
from models_crm import Activity, APIKey, Company, Contact, Deal, OAuthClient, Task
from services.api_auth_service import APIAuthService, api_auth_required
from services.webhook_service import WebhookService


bp = Blueprint('public_api', __name__)


def _pagination_params(default_limit: int = 50, max_limit: int = 100):
    try:
        limit = int(request.args.get('limit', default_limit))
    except (TypeError, ValueError):
        limit = default_limit

    try:
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0

    limit = max(1, min(max_limit, limit))
    offset = max(0, offset)
    return limit, offset


def _api_success(data, limit=None, offset=None, total=None):
    payload = {'data': data}
    if limit is not None:
        payload['pagination'] = {
            'limit': limit,
            'offset': offset,
            'total': total,
        }
    return jsonify(payload), 200


def _agent_session_required(f):
    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        if not session.get('workspace_id'):
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------------------
# API auth management (internal agent/admin session)
# ---------------------------------------------------------------------------


@bp.route('/api/v1/public-auth/api-keys', methods=['POST'])
@_agent_session_required
def create_api_key():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    scopes = data.get('scopes') or 'read'
    expires_in_days = data.get('expires_in_days')

    if not name:
        return jsonify({'error': 'name is required'}), 400

    expires_at = None
    if expires_in_days is not None:
        try:
            days = int(expires_in_days)
            if days <= 0:
                return jsonify({'error': 'expires_in_days must be > 0'}), 400
            from datetime import datetime, timedelta
            expires_at = datetime.utcnow() + timedelta(days=days)
        except (TypeError, ValueError):
            return jsonify({'error': 'expires_in_days must be integer'}), 400

    record, plaintext_key = APIAuthService.generate_api_key(
        workspace_id=workspace_id,
        name=name,
        created_by=user_id,
        scopes=scopes,
        expires_at=expires_at,
    )

    return jsonify({
        'id': record.id,
        'name': record.name,
        'scopes': record.scopes,
        'key_prefix': record.key_prefix,
        'api_key': plaintext_key,
        'expires_at': record.expires_at.isoformat() if record.expires_at else None,
        'created_at': record.created_at.isoformat(),
        'note': 'Store this API key securely. It will not be shown again.',
    }), 201


@bp.route('/api/v1/public-auth/api-keys', methods=['GET'])
@_agent_session_required
def list_api_keys():
    workspace_id = session.get('workspace_id')
    records = APIKey.query.filter_by(workspace_id=workspace_id).order_by(APIKey.created_at.desc()).all()

    return jsonify({
        'api_keys': [
            {
                'id': record.id,
                'name': record.name,
                'key_prefix': record.key_prefix,
                'scopes': record.scopes,
                'is_active': record.is_active,
                'last_used_at': record.last_used_at.isoformat() if record.last_used_at else None,
                'expires_at': record.expires_at.isoformat() if record.expires_at else None,
                'created_at': record.created_at.isoformat(),
            }
            for record in records
        ]
    }), 200


@bp.route('/api/v1/public-auth/api-keys/<int:api_key_id>', methods=['DELETE'])
@_agent_session_required
def revoke_api_key(api_key_id):
    workspace_id = session.get('workspace_id')
    record = APIAuthService.deactivate_api_key(workspace_id, api_key_id)
    if not record:
        return jsonify({'error': 'API key not found'}), 404

    return jsonify({'status': 'revoked', 'id': record.id}), 200


@bp.route('/api/v1/public-auth/oauth-clients', methods=['POST'])
@_agent_session_required
def create_oauth_client():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    redirect_uris = data.get('redirect_uris') or []
    scopes = data.get('scopes') or 'read'

    if not name:
        return jsonify({'error': 'name is required'}), 400
    if not isinstance(redirect_uris, list) or not redirect_uris:
        return jsonify({'error': 'redirect_uris must be non-empty array'}), 400

    client, plaintext_secret = APIAuthService.create_oauth_client(
        workspace_id=workspace_id,
        name=name,
        redirect_uris=redirect_uris,
        created_by=user_id,
        scopes=scopes,
    )

    return jsonify({
        'id': client.id,
        'name': client.name,
        'client_id': client.client_id,
        'client_secret': plaintext_secret,
        'redirect_uris': redirect_uris,
        'scopes': client.scopes,
        'note': 'Store this client_secret securely. It will not be shown again.',
    }), 201


@bp.route('/api/v1/public-auth/oauth-clients', methods=['GET'])
@_agent_session_required
def list_oauth_clients():
    workspace_id = session.get('workspace_id')
    clients = OAuthClient.query.filter_by(workspace_id=workspace_id).order_by(OAuthClient.created_at.desc()).all()

    import json

    return jsonify({
        'oauth_clients': [
            {
                'id': client.id,
                'name': client.name,
                'client_id': client.client_id,
                'redirect_uris': json.loads(client.redirect_uris or '[]'),
                'scopes': client.scopes,
                'is_active': client.is_active,
                'created_at': client.created_at.isoformat(),
            }
            for client in clients
        ]
    }), 200


@bp.route('/api/v1/public-auth/oauth-clients/<int:client_row_id>', methods=['DELETE'])
@_agent_session_required
def deactivate_oauth_client(client_row_id):
    workspace_id = session.get('workspace_id')
    client, revoked_count = APIAuthService.deactivate_oauth_client(workspace_id, client_row_id)
    if not client:
        return jsonify({'error': 'OAuth client not found'}), 404

    return jsonify({
        'status': 'deactivated',
        'id': client.id,
        'revoked_tokens': revoked_count,
    }), 200


@bp.route('/api/v1/public-auth/webhooks', methods=['POST'])
@_agent_session_required
def create_webhook_subscription():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    target_url = (data.get('target_url') or '').strip()
    event_types = data.get('event_types') or []

    if not name:
        return jsonify({'error': 'name is required'}), 400
    if not target_url:
        return jsonify({'error': 'target_url is required'}), 400

    try:
        subscription = WebhookService.create_subscription(
            workspace_id=workspace_id,
            name=name,
            target_url=target_url,
            event_types=event_types,
            created_by=user_id,
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    payload = WebhookService.serialize_subscription(subscription)
    payload['secret'] = subscription.secret
    payload['note'] = 'Webhook secret is shown once. Store it securely.'
    return jsonify(payload), 201


@bp.route('/api/v1/public-auth/webhooks', methods=['GET'])
@_agent_session_required
def list_webhook_subscriptions():
    workspace_id = session.get('workspace_id')
    rows = WebhookService.list_subscriptions(workspace_id)
    return jsonify({'webhooks': [WebhookService.serialize_subscription(row) for row in rows]}), 200


@bp.route('/api/v1/public-auth/webhooks/<int:subscription_id>', methods=['PUT'])
@_agent_session_required
def update_webhook_subscription(subscription_id):
    workspace_id = session.get('workspace_id')
    data = request.get_json(silent=True) or {}

    subscription = WebhookService.get_subscription(workspace_id, subscription_id)
    if not subscription:
        return jsonify({'error': 'Webhook subscription not found'}), 404

    try:
        updated = WebhookService.update_subscription(
            subscription,
            name=data.get('name'),
            target_url=data.get('target_url'),
            event_types=data.get('event_types'),
            is_active=data.get('is_active'),
            rotate_secret=data.get('rotate_secret', False),
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    payload = WebhookService.serialize_subscription(updated)
    if data.get('rotate_secret'):
        payload['secret'] = updated.secret
        payload['note'] = 'Secret rotated. Store the new secret securely.'
    return jsonify(payload), 200


@bp.route('/api/v1/public-auth/webhooks/<int:subscription_id>', methods=['DELETE'])
@_agent_session_required
def delete_webhook_subscription(subscription_id):
    workspace_id = session.get('workspace_id')
    subscription = WebhookService.get_subscription(workspace_id, subscription_id)
    if not subscription:
        return jsonify({'error': 'Webhook subscription not found'}), 404

    WebhookService.delete_subscription(subscription)
    return jsonify({'status': 'deleted'}), 200


@bp.route('/api/v1/public-auth/webhooks/<int:subscription_id>/deliveries', methods=['GET'])
@_agent_session_required
def list_webhook_deliveries(subscription_id):
    workspace_id = session.get('workspace_id')
    limit = request.args.get('limit', 50)

    subscription = WebhookService.get_subscription(workspace_id, subscription_id)
    if not subscription:
        return jsonify({'error': 'Webhook subscription not found'}), 404

    rows = WebhookService.list_deliveries(workspace_id, subscription_id, limit=limit)
    return jsonify({'deliveries': [WebhookService.serialize_delivery(row) for row in rows]}), 200


@bp.route('/api/v1/public-auth/webhooks/<int:subscription_id>/test', methods=['POST'])
@_agent_session_required
def test_webhook_delivery(subscription_id):
    workspace_id = session.get('workspace_id')

    subscription = WebhookService.get_subscription(workspace_id, subscription_id)
    if not subscription:
        return jsonify({'error': 'Webhook subscription not found'}), 404

    delivery = WebhookService.trigger_test_delivery(workspace_id, subscription)
    payload = WebhookService.serialize_delivery(delivery)
    return jsonify(payload), 200


# ---------------------------------------------------------------------------
# OAuth2 authorization code flow
# ---------------------------------------------------------------------------


@bp.route('/public/oauth/authorize', methods=['GET'])
@_agent_session_required
def oauth_authorize():
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')

    response_type = request.args.get('response_type')
    client_id = request.args.get('client_id')
    redirect_uri = request.args.get('redirect_uri')
    scope = request.args.get('scope', 'read')
    state = request.args.get('state')

    if response_type != 'code':
        return jsonify({'error': 'unsupported_response_type'}), 400

    client = APIAuthService.get_oauth_client(client_id)
    if not client or client.workspace_id != workspace_id:
        return jsonify({'error': 'invalid_client'}), 400

    if not APIAuthService.validate_redirect_uri(client, redirect_uri):
        return jsonify({'error': 'invalid_redirect_uri'}), 400

    auth_code = APIAuthService.issue_authorization_code(
        client=client,
        workspace_id=workspace_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        scopes=scope,
    )

    query = {'code': auth_code}
    if state:
        query['state'] = state
    redirect_target = f"{redirect_uri}?{urlencode(query)}"
    return redirect(redirect_target, code=302)


@bp.route('/public/oauth/token', methods=['POST'])
def oauth_token():
    data = request.get_json(silent=True) if request.is_json else request.form

    grant_type = data.get('grant_type') if data else None
    code = data.get('code') if data else None
    client_id = data.get('client_id') if data else None
    client_secret = data.get('client_secret') if data else None
    redirect_uri = data.get('redirect_uri') if data else None

    if grant_type != 'authorization_code':
        return jsonify({'error': 'unsupported_grant_type'}), 400

    client = APIAuthService.get_oauth_client(client_id)
    if not client:
        return jsonify({'error': 'invalid_client'}), 401

    if not APIAuthService.validate_oauth_client_secret(client, client_secret):
        return jsonify({'error': 'invalid_client'}), 401

    if not APIAuthService.validate_redirect_uri(client, redirect_uri):
        return jsonify({'error': 'invalid_grant'}), 400

    token_payload = APIAuthService.exchange_authorization_code(
        client=client,
        raw_code=code,
        redirect_uri=redirect_uri,
    )

    if not token_payload:
        return jsonify({'error': 'invalid_grant'}), 400

    return jsonify(token_payload), 200


@bp.route('/public/oauth/revoke', methods=['POST'])
def oauth_revoke_token():
    data = request.get_json(silent=True) if request.is_json else request.form

    token = data.get('token') if data else None
    client_id = data.get('client_id') if data else None
    client_secret = data.get('client_secret') if data else None

    client = APIAuthService.get_oauth_client(client_id)
    if not client:
        return jsonify({'error': 'invalid_client'}), 401

    if not APIAuthService.validate_oauth_client_secret(client, client_secret):
        return jsonify({'error': 'invalid_client'}), 401

    APIAuthService.revoke_oauth_access_token(client, token)
    return jsonify({'status': 'revoked'}), 200


# ---------------------------------------------------------------------------
# Public REST API (API key or OAuth bearer token)
# ---------------------------------------------------------------------------


@bp.route('/public/api/v1/contacts', methods=['GET'])
@api_auth_required('read')
def public_contacts():
    workspace_id = g.api_workspace_id
    limit, offset = _pagination_params()

    query = Contact.query.filter_by(workspace_id=workspace_id, is_deleted=False)
    total = query.count()
    rows = query.order_by(Contact.created_at.desc()).offset(offset).limit(limit).all()

    return _api_success([
        {
            'id': row.id,
            'company_id': row.company_id,
            'first_name': row.first_name,
            'last_name': row.last_name,
            'full_name': row.full_name,
            'email': row.email,
            'phone': row.phone,
            'role': row.role,
            'job_title': row.job_title,
            'lead_score': row.lead_score,
            'created_at': row.created_at.isoformat(),
        }
        for row in rows
    ], limit=limit, offset=offset, total=total)


@bp.route('/public/api/v1/companies', methods=['GET'])
@api_auth_required('read')
def public_companies():
    workspace_id = g.api_workspace_id
    limit, offset = _pagination_params()

    query = Company.query.filter_by(workspace_id=workspace_id, is_deleted=False)
    total = query.count()
    rows = query.order_by(Company.created_at.desc()).offset(offset).limit(limit).all()

    return _api_success([
        {
            'id': row.id,
            'name': row.name,
            'industry': row.industry,
            'size': row.size,
            'website': row.website,
            'phone': row.phone,
            'address': row.address,
            'created_at': row.created_at.isoformat(),
        }
        for row in rows
    ], limit=limit, offset=offset, total=total)


@bp.route('/public/api/v1/deals', methods=['GET'])
@api_auth_required('read')
def public_deals():
    workspace_id = g.api_workspace_id
    limit, offset = _pagination_params()

    query = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False)
    total = query.count()
    rows = query.order_by(Deal.updated_at.desc()).offset(offset).limit(limit).all()

    return _api_success([
        {
            'id': row.id,
            'name': row.name,
            'company_id': row.company_id,
            'pipeline_id': row.pipeline_id,
            'stage_id': row.stage_id,
            'stage_name': row.stage.name if row.stage else None,
            'value': float(row.value),
            'status': row.status,
            'expected_close_date': row.expected_close_date.isoformat() if row.expected_close_date else None,
            'closed_at': row.closed_at.isoformat() if row.closed_at else None,
            'updated_at': row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ], limit=limit, offset=offset, total=total)


@bp.route('/public/api/v1/tasks', methods=['GET'])
@api_auth_required('read')
def public_tasks():
    workspace_id = g.api_workspace_id
    limit, offset = _pagination_params()

    query = Task.query.filter_by(workspace_id=workspace_id)
    total = query.count()
    rows = query.order_by(Task.updated_at.desc()).offset(offset).limit(limit).all()

    return _api_success([
        {
            'id': row.id,
            'title': row.title,
            'description': row.description,
            'assignee_id': row.assignee_id,
            'company_id': row.company_id,
            'deal_id': row.deal_id,
            'milestone_id': row.milestone_id,
            'status': row.status,
            'priority': row.priority,
            'due_date': row.due_date.isoformat() if row.due_date else None,
            'is_customer_facing': row.is_customer_facing,
            'completed_at': row.completed_at.isoformat() if row.completed_at else None,
            'updated_at': row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ], limit=limit, offset=offset, total=total)


@bp.route('/public/api/v1/activities', methods=['GET'])
@api_auth_required('read')
def public_activities():
    workspace_id = g.api_workspace_id
    limit, offset = _pagination_params()

    query = Activity.query.filter_by(workspace_id=workspace_id, is_deleted=False)
    total = query.count()
    rows = query.order_by(Activity.created_at.desc()).offset(offset).limit(limit).all()

    user_ids = [row.user_id for row in rows if row.user_id]
    users = {user.id: user for user in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    return _api_success([
        {
            'id': row.id,
            'activity_type': row.activity_type,
            'contact_id': row.contact_id,
            'company_id': row.company_id,
            'deal_id': row.deal_id,
            'user_id': row.user_id,
            'user_name': users[row.user_id].name if row.user_id in users else None,
            'subject': row.subject,
            'body': row.body,
            'created_at': row.created_at.isoformat(),
        }
        for row in rows
    ], limit=limit, offset=offset, total=total)
