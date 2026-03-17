"""
Contact Management Routes
API endpoints for companies and contacts
"""
from flask import Blueprint, request, jsonify, session, make_response
from functools import wraps
from services.contact_service import ContactService
from services.collaboration_service import CollaborationService
import logging

logger = logging.getLogger(__name__)

contacts_bp = Blueprint('contacts', __name__)


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# COMPANY ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/companies', methods=['GET'])
@login_required
def get_companies():
    """Get all companies with optional filters"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        # Get filters from query params
        filters = {}
        if request.args.get('industry'):
            filters['industry'] = request.args.get('industry')
        if request.args.get('size'):
            filters['size'] = request.args.get('size')
        if request.args.get('search'):
            filters['search'] = request.args.get('search')
        
        companies = ContactService.get_companies(workspace_id, filters)
        
        return jsonify({
            'companies': [
                {
                    'id': c.id,
                    'name': c.name,
                    'industry': c.industry,
                    'size': c.size,
                    'website': c.website,
                    'phone': c.phone,
                    'address': c.address,
                    'parent_company_id': c.parent_company_id,
                    'parent_company_name': c.parent_company.name if c.parent_company else None,
                    'created_at': c.created_at.isoformat() if c.created_at else None,
                    'updated_at': c.updated_at.isoformat() if c.updated_at else None
                }
                for c in companies
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting companies: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/v1/companies/<int:company_id>', methods=['GET'])
@login_required
def get_company(company_id):
    """Get a single company by ID"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Company
        company = Company.query.filter_by(
            id=company_id,
            workspace_id=workspace_id
        ).first()
        
        if not company:
            return jsonify({'error': 'Company not found'}), 404
        
        # Get custom fields
        custom_fields = ContactService.get_custom_field_values(
            workspace_id, 'company', company_id
        )
        
        return jsonify({
            'id': company.id,
            'name': company.name,
            'industry': company.industry,
            'size': company.size,
            'website': company.website,
            'phone': company.phone,
            'address': company.address,
            'parent_company_id': company.parent_company_id,
            'parent_company_name': company.parent_company.name if company.parent_company else None,
            'custom_fields': custom_fields,
            'created_at': company.created_at.isoformat() if company.created_at else None,
            'updated_at': company.updated_at.isoformat() if company.updated_at else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting company: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/v1/companies', methods=['POST'])
@login_required
def create_company():
    """Create a new company"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        company = ContactService.create_company(workspace_id, data, user_id)
        
        return jsonify({
            'id': company.id,
            'name': company.name,
            'industry': company.industry,
            'size': company.size,
            'website': company.website,
            'phone': company.phone,
            'address': company.address,
            'parent_company_id': company.parent_company_id,
            'created_at': company.created_at.isoformat() if company.created_at else None
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating company: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/v1/companies/<int:company_id>', methods=['PATCH'])
@login_required
def update_company(company_id):
    """Update a company"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        company = ContactService.update_company(workspace_id, company_id, data, user_id)
        
        return jsonify({
            'id': company.id,
            'name': company.name,
            'industry': company.industry,
            'size': company.size,
            'website': company.website,
            'phone': company.phone,
            'address': company.address,
            'parent_company_id': company.parent_company_id,
            'updated_at': company.updated_at.isoformat() if company.updated_at else None
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating company: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# CONTACT ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/contacts', methods=['GET'])
@login_required
def get_contacts():
    """Get all contacts with optional filters"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        # Get filters from query params
        filters = {}
        if request.args.get('company_id'):
            filters['company_id'] = int(request.args.get('company_id'))
        if request.args.get('role'):
            filters['role'] = request.args.get('role')
        if request.args.get('search'):
            filters['search'] = request.args.get('search')
        
        contacts = ContactService.get_contacts(workspace_id, filters)
        
        return jsonify({
            'contacts': [
                {
                    'id': c.id,
                    'first_name': c.first_name,
                    'last_name': c.last_name,
                    'full_name': c.full_name,
                    'email': c.email,
                    'phone': c.phone,
                    'whatsapp_phone': c.whatsapp_phone,
                    'role': c.role,
                    'job_title': c.job_title,
                    'lead_score': c.lead_score,
                    'company_id': c.company_id,
                    'company_name': c.company.name if c.company else None,
                    'created_at': c.created_at.isoformat() if c.created_at else None,
                    'updated_at': c.updated_at.isoformat() if c.updated_at else None
                }
                for c in contacts
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting contacts: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>', methods=['GET'])
@login_required
def get_contact(contact_id):
    """Get a single contact by ID"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Contact
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Get custom fields
        custom_fields = ContactService.get_custom_field_values(
            workspace_id, 'contact', contact_id
        )
        
        return jsonify({
            'id': contact.id,
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'full_name': contact.full_name,
            'email': contact.email,
            'phone': contact.phone,
            'whatsapp_phone': contact.whatsapp_phone,
            'role': contact.role,
            'job_title': contact.job_title,
            'lead_score': contact.lead_score,
            'company_id': contact.company_id,
            'company_name': contact.company.name if contact.company else None,
            'custom_fields': custom_fields,
            'created_at': contact.created_at.isoformat() if contact.created_at else None,
            'updated_at': contact.updated_at.isoformat() if contact.updated_at else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting contact: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/v1/contacts', methods=['POST'])
@login_required
def create_contact():
    """Create a new contact"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        contact = ContactService.create_contact(workspace_id, data, user_id)
        
        # Calculate lead score
        lead_score = ContactService.calculate_lead_score(contact)
        contact.lead_score = lead_score
        from models import db
        db.session.commit()

        try:
            from services.webhook_service import WebhookService
            WebhookService.dispatch_event(workspace_id, 'contact.created', {
                'contact_id': contact.id,
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'full_name': contact.full_name,
                'email': contact.email,
                'phone': contact.phone,
                'company_id': contact.company_id,
                'created_at': contact.created_at.isoformat() if contact.created_at else None,
            })
        except Exception as exc:
            logger.warning('Webhook dispatch failed for contact.created: %s', exc)
        
        return jsonify({
            'id': contact.id,
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'full_name': contact.full_name,
            'email': contact.email,
            'phone': contact.phone,
            'whatsapp_phone': contact.whatsapp_phone,
            'role': contact.role,
            'job_title': contact.job_title,
            'lead_score': contact.lead_score,
            'company_id': contact.company_id,
            'created_at': contact.created_at.isoformat() if contact.created_at else None
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating contact: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/v1/contacts/<int:contact_id>', methods=['PATCH'])
@login_required
def update_contact(contact_id):
    """Update a contact"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        contact = ContactService.update_contact(workspace_id, contact_id, data, user_id)
        
        # Recalculate lead score
        lead_score = ContactService.calculate_lead_score(contact)
        contact.lead_score = lead_score
        from models import db
        db.session.commit()

        CollaborationService.notify_followers_on_entity_change(
            workspace_id=workspace_id,
            entity_type='contact',
            entity_id=contact.id,
            message=f'Takip ettiginiz kisi guncellendi: {contact.full_name}',
        )
        
        return jsonify({
            'id': contact.id,
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'full_name': contact.full_name,
            'email': contact.email,
            'phone': contact.phone,
            'whatsapp_phone': contact.whatsapp_phone,
            'role': contact.role,
            'job_title': contact.job_title,
            'lead_score': contact.lead_score,
            'company_id': contact.company_id,
            'updated_at': contact.updated_at.isoformat() if contact.updated_at else None
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating contact: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# CSV IMPORT/EXPORT ENDPOINTS
# ============================================================================

@contacts_bp.route('/api/v1/contacts/export', methods=['GET'])
@login_required
def export_contacts():
    """Export contacts to CSV"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        # Get filters from query params
        filters = {}
        if request.args.get('company_id'):
            filters['company_id'] = int(request.args.get('company_id'))
        if request.args.get('role'):
            filters['role'] = request.args.get('role')
        if request.args.get('search'):
            filters['search'] = request.args.get('search')
        
        csv_content = ContactService.export_contacts_csv(workspace_id, filters)
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=contacts.csv'
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting contacts: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/v1/contacts/import', methods=['POST'])
@login_required
def import_contacts():
    """Import contacts from CSV"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400
        
        # Read CSV content
        csv_content = file.read().decode('utf-8')
        
        # Import contacts
        created_count, skipped_count, errors = ContactService.import_contacts_csv(
            workspace_id, csv_content, user_id
        )
        
        return jsonify({
            'created': created_count,
            'skipped': skipped_count,
            'errors': errors
        }), 200
        
    except Exception as e:
        logger.error(f"Error importing contacts: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/v1/companies/export', methods=['GET'])
@login_required
def export_companies():
    """Export companies to CSV"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        # Get filters from query params
        filters = {}
        if request.args.get('industry'):
            filters['industry'] = request.args.get('industry')
        if request.args.get('size'):
            filters['size'] = request.args.get('size')
        if request.args.get('search'):
            filters['search'] = request.args.get('search')
        
        csv_content = ContactService.export_companies_csv(workspace_id, filters)
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=companies.csv'
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting companies: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# BULK OPERATIONS
# ============================================================================

@contacts_bp.route('/api/v1/contacts/bulk-update', methods=['POST'])
@login_required
def bulk_update_contacts():
    """Bulk update multiple contacts"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        contact_ids = data.get('contact_ids', [])
        updates = data.get('updates', {})
        
        if not contact_ids:
            return jsonify({'error': 'No contact IDs provided'}), 400
        
        if not updates:
            return jsonify({'error': 'No updates provided'}), 400
        
        # Validate contact IDs belong to workspace
        from models_crm import Contact
        from models import db
        
        contacts = Contact.query.filter(
            Contact.id.in_(contact_ids),
            Contact.workspace_id == workspace_id
        ).all()
        
        if len(contacts) != len(contact_ids):
            return jsonify({'error': 'Some contacts not found'}), 404
        
        # Update each contact
        updated_count = 0
        for contact in contacts:
            try:
                # Apply updates
                for field, value in updates.items():
                    if hasattr(contact, field):
                        setattr(contact, field, value)
                
                # Recalculate lead score if relevant fields changed
                if any(f in updates for f in ['email', 'phone', 'role', 'company_id']):
                    contact.lead_score = ContactService.calculate_lead_score(contact)
                
                updated_count += 1
            except Exception as e:
                logger.error(f"Error updating contact {contact.id}: {str(e)}")
                continue
        
        db.session.commit()
        
        return jsonify({
            'updated': updated_count,
            'total': len(contact_ids)
        }), 200
        
    except Exception as e:
        logger.error(f"Error bulk updating contacts: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/v1/contacts/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_contacts():
    """Bulk delete multiple contacts"""
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        contact_ids = data.get('contact_ids', [])
        
        if not contact_ids:
            return jsonify({'error': 'No contact IDs provided'}), 400
        
        # Validate and delete contacts
        from models_crm import Contact
        from models import db
        
        deleted_count = Contact.query.filter(
            Contact.id.in_(contact_ids),
            Contact.workspace_id == workspace_id
        ).delete(synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({
            'deleted': deleted_count,
            'total': len(contact_ids)
        }), 200
        
    except Exception as e:
        logger.error(f"Error bulk deleting contacts: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# USER PREFERENCES
# ============================================================================

@contacts_bp.route('/api/v1/user-preferences/contacts-columns', methods=['GET'])
@login_required
def get_contacts_column_preferences():
    """Get user's column preferences for contacts table"""
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not user_id or not workspace_id:
            return jsonify({'error': 'User or workspace not found'}), 400
        
        from models import db
        from sqlalchemy import text
        
        # Try to get from database
        result = db.session.execute(
            text("SELECT preference_value FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_visible_columns'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            import json
            return jsonify({'columns': json.loads(result[0])}), 200
        
        # Return default columns
        default_columns = [
            'name', 'company', 'email', 'phone', 'role', 'lead_score', 'deals'
        ]
        
        return jsonify({'columns': default_columns}), 200
        
    except Exception as e:
        logger.error(f"Error getting column preferences: {str(e)}")
        # Return defaults on error
        return jsonify({'columns': ['name', 'company', 'email', 'phone', 'role', 'lead_score', 'deals']}), 200


@contacts_bp.route('/api/v1/user-preferences/contacts-columns', methods=['POST'])
@login_required
def save_contacts_column_preferences():
    """Save user's column preferences for contacts table"""
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not user_id or not workspace_id:
            return jsonify({'error': 'User or workspace not found'}), 400
        
        data = request.get_json()
        if not data or 'columns' not in data:
            return jsonify({'error': 'No columns provided'}), 400
        
        columns = data['columns']
        
        from models import db
        from sqlalchemy import text
        import json
        
        # Check if preference exists
        result = db.session.execute(
            text("SELECT id FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_visible_columns'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            # Update existing
            db.session.execute(
                text("UPDATE user_preferences SET preference_value = :value, updated_at = CURRENT_TIMESTAMP WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_visible_columns'"),
                {'value': json.dumps(columns), 'user_id': user_id, 'workspace_id': workspace_id}
            )
        else:
            # Insert new
            db.session.execute(
                text("INSERT INTO user_preferences (user_id, workspace_id, preference_key, preference_value, created_at, updated_at) VALUES (:user_id, :workspace_id, 'contacts_visible_columns', :value, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                {'user_id': user_id, 'workspace_id': workspace_id, 'value': json.dumps(columns)}
            )
        
        db.session.commit()
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        logger.error(f"Error saving column preferences: {str(e)}")
        return jsonify({'error': str(e)}), 500
