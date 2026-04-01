"""
Forms API Routes
Public form submission and authenticated form management.
"""
from flask import Blueprint, request, jsonify, render_template, current_app, session
from datetime import datetime
import json
from functools import wraps

from models import User

from services.form_service import (
    create_web_form, list_web_forms, get_web_form_by_id,
    update_web_form, delete_web_form, process_submission,
    list_form_submissions, get_embed_code, get_form_for_public,
    get_default_fields
)

forms_bp = Blueprint('forms', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        user = User.query.get(user_id)
        if not user:
            session.clear()
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


def get_workspace_id():
    """Get workspace ID from current user."""
    current_user = get_current_user()
    if current_user and hasattr(current_user, 'workspace_id'):
        return current_user.workspace_id
    return None


# =============================================================================
# PUBLIC ROUTES (No auth required)
# =============================================================================

@forms_bp.route('/f/<int:form_id>')
def public_form_page(form_id):
    """Public form page - render HTML form."""
    form = get_form_for_public(form_id)
    if not form:
        return "Form not found or inactive.", 404
    
    try:
        fields = json.loads(form.fields_json) if form.fields_json else []
    except json.JSONDecodeError:
        fields = []
    
    return render_template(
        'public/form.html',
        form=form,
        fields=fields
    )


@forms_bp.route('/api/v1/public/forms/<int:form_id>/submit', methods=['POST'])
def public_submit_form(form_id):
    """Submit a form (public - no auth required, CSRF exempt)."""
    form = get_form_for_public(form_id)
    if not form:
        return jsonify({'error': 'Form not found or inactive'}), 404
    
    # Get form data
    data = request.get_json() or request.form.to_dict()
    
    # Add IP and user agent for tracking
    data['_ip'] = request.remote_addr
    data['_user_agent'] = request.headers.get('User-Agent', '')[:500]
    
    try:
        success, contact, errors, redirect_url = process_submission(
            form_id=form_id,
            data_dict=data,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500]
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Form submitted successfully!',
                'redirect_url': redirect_url,
                'contact_id': contact.id if contact else None
            })
        else:
            return jsonify({
                'success': False,
                'errors': errors
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Form submission failed: {e}")
        return jsonify({'error': 'Form submission failed. Please try again.'}), 500


# =============================================================================
# AUTHENTICATED ROUTES (CRM Internal)
# =============================================================================

@forms_bp.route('/api/v1/forms', methods=['GET'])
@login_required
def api_list_forms():
    """List all forms for current user's workspace."""
    workspace_id = get_workspace_id()
    if not workspace_id:
        return jsonify({'error': 'Workspace not found'}), 400
    
    forms = list_web_forms(workspace_id)
    
    return jsonify({
        'forms': [form.to_dict() for form in forms]
    })


@forms_bp.route('/api/v1/forms', methods=['POST'])
@login_required
def api_create_form():
    """Create a new web form."""
    workspace_id = get_workspace_id()
    if not workspace_id:
        return jsonify({'error': 'Workspace not found'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    
    # Get fields
    fields_json = data.get('fields_json')
    if fields_json:
        # Validate it's valid JSON
        try:
            json.loads(fields_json)
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid fields JSON'}), 400
    
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Authentication required'}), 401

        form = create_web_form(
            workspace_id=workspace_id,
            name=name,
            created_by=current_user.id,
            fields_json=fields_json or json.dumps(get_default_fields()),
            submit_action=data.get('submit_action', 'create_contact'),
            redirect_url=data.get('redirect_url'),
            notify_user_id=data.get('notify_user_id')
        )
        
        return jsonify({
            'success': True,
            'form': form.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Create form failed: {e}")
        return jsonify({'error': 'Failed to create form'}), 500


@forms_bp.route('/api/v1/forms/<int:form_id>', methods=['GET'])
@login_required
def api_get_form(form_id):
    """Get a specific form."""
    form = get_web_form_by_id(form_id)
    if not form:
        return jsonify({'error': 'Form not found'}), 404
    
    # Check workspace access
    if form.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'form': form.to_dict()
    })


@forms_bp.route('/api/v1/forms/<int:form_id>', methods=['PATCH'])
@login_required
def api_update_form(form_id):
    """Update a form."""
    form = get_web_form_by_id(form_id)
    if not form:
        return jsonify({'error': 'Form not found'}), 404
    
    # Check workspace access
    if form.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Validate fields_json if provided
    if 'fields_json' in data:
        try:
            json.loads(data['fields_json'])
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid fields JSON'}), 400
    
    try:
        updated = update_web_form(
            form_id=form_id,
            name=data.get('name'),
            fields_json=data.get('fields_json'),
            submit_action=data.get('submit_action'),
            redirect_url=data.get('redirect_url'),
            notify_user_id=data.get('notify_user_id'),
            is_active=data.get('is_active')
        )
        
        return jsonify({
            'success': True,
            'form': updated.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Update form failed: {e}")
        return jsonify({'error': 'Failed to update form'}), 500


@forms_bp.route('/api/v1/forms/<int:form_id>', methods=['DELETE'])
@login_required
def api_delete_form(form_id):
    """Delete a form."""
    form = get_web_form_by_id(form_id)
    if not form:
        return jsonify({'error': 'Form not found'}), 404
    
    # Check workspace access
    if form.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        delete_web_form(form_id)
        return jsonify({'success': True, 'message': 'Form deleted'})
        
    except Exception as e:
        current_app.logger.error(f"Delete form failed: {e}")
        return jsonify({'error': 'Failed to delete form'}), 500


@forms_bp.route('/api/v1/forms/<int:form_id>/submissions', methods=['GET'])
@login_required
def api_list_submissions(form_id):
    """List submissions for a form."""
    form = get_web_form_by_id(form_id)
    if not form:
        return jsonify({'error': 'Form not found'}), 404
    
    # Check workspace access
    if form.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    submissions, total = list_form_submissions(form_id, page, per_page)
    
    return jsonify({
        'submissions': [s.to_dict() for s in submissions],
        'total': total,
        'page': page,
        'per_page': per_page
    })


@forms_bp.route('/api/v1/forms/<int:form_id>/embed-code', methods=['GET'])
@login_required
def api_get_embed_code(form_id):
    """Get embed code for a form."""
    form = get_web_form_by_id(form_id)
    if not form:
        return jsonify({'error': 'Form not found'}), 404
    
    # Check workspace access
    if form.workspace_id != get_workspace_id():
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'embed_code': get_embed_code(form_id),
        'form_url': f'/f/{form_id}'
    })


@forms_bp.route('/api/v1/forms/default-fields', methods=['GET'])
@login_required
def api_get_default_fields():
    """Get default form fields template."""
    from services.form_service import get_default_fields
    return jsonify({
        'fields': get_default_fields()
    })
