from datetime import date
from io import BytesIO
from functools import wraps

from flask import Blueprint, jsonify, request, send_file, session

from models_crm import Company, Contact, Deal
from services.document_service import DocumentService


documents_bp = Blueprint('documents', __name__, url_prefix='/api/v1/documents')


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)

    return decorated


def write_access_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        role = (session.get('user_role') or '').lower()
        if role in {'read-only', 'readonly'}:
            return jsonify({'success': False, 'error': 'Write permission required'}), 403
        return f(*args, **kwargs)

    return decorated


def _workspace_id():
    return session.get('workspace_id')


def _user_id():
    return session.get('user_id')


@documents_bp.route('', methods=['GET'])
@login_required
def list_documents():
    workspace_id = _workspace_id()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    category = request.args.get('category')

    payload = DocumentService.list_documents(
        workspace_id=workspace_id,
        category=category,
        page=page,
        per_page=per_page,
    )
    return jsonify({'success': True, 'data': payload})


@documents_bp.route('', methods=['POST'])
@write_access_required
def upload_document():
    workspace_id = _workspace_id()
    user_id = _user_id()

    file_storage = request.files.get('file')
    name = request.form.get('name')
    category = request.form.get('category', 'general')
    company_id = request.form.get('company_id', type=int)
    deal_id = request.form.get('deal_id', type=int)
    is_customer_visible = request.form.get('is_customer_visible', 'false').lower() == 'true'

    try:
        doc = DocumentService.create_document(
            workspace_id=workspace_id,
            uploaded_by=user_id,
            file_storage=file_storage,
            name=name,
            category=category,
            company_id=company_id,
            deal_id=deal_id,
            is_customer_visible=is_customer_visible,
        )
        return jsonify({'success': True, 'data': {'id': doc.id, 'name': doc.name}}), 201
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@documents_bp.route('/<int:document_id>/versions', methods=['POST'])
@write_access_required
def upload_document_version(document_id):
    workspace_id = _workspace_id()
    user_id = _user_id()
    file_storage = request.files.get('file')

    try:
        version = DocumentService.add_version(
            workspace_id=workspace_id,
            document_id=document_id,
            uploaded_by=user_id,
            file_storage=file_storage,
        )
        return jsonify({'success': True, 'data': {'id': version.id, 'version_number': version.version_number}}), 201
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@documents_bp.route('/<int:document_id>/versions', methods=['GET'])
@login_required
def list_document_versions(document_id):
    workspace_id = _workspace_id()
    try:
        versions = DocumentService.get_document_versions(workspace_id, document_id)
        return jsonify({'success': True, 'data': versions})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404


@documents_bp.route('/<int:document_id>/download', methods=['GET'])
@login_required
def download_document(document_id):
    workspace_id = _workspace_id()
    version_id = request.args.get('version_id', type=int)

    try:
        payload = DocumentService.get_file_payload(workspace_id, document_id, version_id)
        return send_file(
            BytesIO(payload['bytes']),
            mimetype=payload['mime_type'],
            as_attachment=True,
            download_name=payload['download_name'],
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404


@documents_bp.route('/templates', methods=['GET'])
@login_required
def list_templates():
    workspace_id = _workspace_id()
    rows = DocumentService.list_document_templates(workspace_id)
    return jsonify({'success': True, 'data': rows})


@documents_bp.route('/templates', methods=['POST'])
@write_access_required
def create_template():
    workspace_id = _workspace_id()
    payload = request.get_json(silent=True) or {}

    name = payload.get('name')
    category = payload.get('category', 'general')
    template_body = payload.get('template_body', '')
    variables = payload.get('variables', [])

    if not name:
        return jsonify({'success': False, 'error': 'Template name is required'}), 400

    row = DocumentService.create_document_template(
        workspace_id=workspace_id,
        name=name,
        category=category,
        template_body=template_body,
        variables=variables,
    )
    return jsonify({'success': True, 'data': {'id': row.id}}), 201


@documents_bp.route('/templates/<int:template_id>/render', methods=['POST'])
@login_required
def render_template(template_id):
    workspace_id = _workspace_id()
    payload = request.get_json(silent=True) or {}
    try:
        rendered = DocumentService.render_saved_template(workspace_id, template_id, payload)
        return jsonify({'success': True, 'data': {'content': rendered}})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404


@documents_bp.route('/template-variables', methods=['GET'])
@login_required
def template_variables():
    """Provide supported merge variables for template rendering."""
    workspace_id = _workspace_id()
    company_id = request.args.get('company_id', type=int)
    contact_id = request.args.get('contact_id', type=int)
    deal_id = request.args.get('deal_id', type=int)

    company_name = ''
    contact_name = ''
    deal_value = ''

    if company_id:
        company = Company.query.filter_by(id=company_id, workspace_id=workspace_id).first()
        if company:
            company_name = company.name

    if contact_id:
        contact = Contact.query.filter_by(id=contact_id, workspace_id=workspace_id).first()
        if contact:
            contact_name = f'{contact.first_name} {contact.last_name}'.strip()

    if deal_id:
        deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id).first()
        if deal and deal.value is not None:
            deal_value = str(deal.value)

    values = {
        'company_name': company_name,
        'contact_name': contact_name,
        'deal_value': deal_value,
        'today_date': date.today().isoformat(),
    }
    return jsonify({'success': True, 'data': values})
