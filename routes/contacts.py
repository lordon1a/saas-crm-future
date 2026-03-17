"""
Contact Management Routes
API endpoints for companies and contacts
"""
from flask import Blueprint, request, jsonify, session, make_response, send_from_directory
from functools import wraps
from services.contact_service import ContactService
from services.collaboration_service import CollaborationService
import logging
import os
import json
import shutil
import time
from datetime import datetime
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)
MAX_CONTACT_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _format_file_size(size_bytes):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / 1024:.2f} KB"

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
    """Get all companies with optional filters and pagination"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 100)  # Max 100 items per page
        
        # Get filters from query params
        filters = {}
        if request.args.get('industry'):
            filters['industry'] = request.args.get('industry')
        if request.args.get('size'):
            filters['size'] = request.args.get('size')
        if request.args.get('search'):
            filters['search'] = request.args.get('search')
        
        # Get paginated companies
        from models_crm import Company
        from models import db
        
        query = Company.query.filter_by(workspace_id=workspace_id)
        
        # Apply filters
        if filters.get('industry'):
            query = query.filter_by(industry=filters['industry'])
        if filters.get('size'):
            query = query.filter_by(size=filters['size'])
        if filters.get('search'):
            search_term = f"%{filters['search']}%"
            query = query.filter(
                db.or_(
                    Company.name.ilike(search_term),
                    Company.website.ilike(search_term),
                    Company.phone.ilike(search_term)
                )
            )
        
        # Eager load parent company
        query = query.options(db.joinedload(Company.parent_company))
        
        # Paginate
        pagination = query.order_by(Company.name).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
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
                for c in pagination.items
            ],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
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
    """Get all contacts with optional filters and pagination"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 100)  # Max 100 items per page
        
        # Get filters from query params
        filters = {}
        if request.args.get('company_id'):
            filters['company_id'] = int(request.args.get('company_id'))
        if request.args.get('role'):
            filters['role'] = request.args.get('role')
        if request.args.get('search'):
            filters['search'] = request.args.get('search')
        
        # Get paginated contacts
        from models_crm import Contact
        from models import db
        
        query = Contact.query.filter_by(workspace_id=workspace_id)
        
        # Apply filters
        if filters.get('company_id'):
            query = query.filter_by(company_id=filters['company_id'])
        if filters.get('role'):
            query = query.filter_by(role=filters['role'])
        if filters.get('search'):
            search_term = f"%{filters['search']}%"
            query = query.filter(
                db.or_(
                    Contact.first_name.ilike(search_term),
                    Contact.last_name.ilike(search_term),
                    Contact.email.ilike(search_term),
                    Contact.phone.ilike(search_term)
                )
            )
        
        # Eager load company
        query = query.options(db.joinedload(Contact.company))
        
        # Paginate
        pagination = query.order_by(Contact.first_name, Contact.last_name).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
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
                for c in pagination.items
            ],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
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


@contacts_bp.route('/contacts/<int:contact_id>')
@login_required
def view_contact_page(contact_id):
    """View contact detail page"""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return redirect('/login')
        
        from models_crm import Contact
        from flask import render_template, redirect
        
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id
        ).first()
        
        if not contact:
            return "Contact not found", 404
        
        return render_template('contact_detail.html', contact=contact)
        
    except Exception as e:
        logger.error(f"Error viewing contact: {str(e)}")
        return str(e), 500


# ============================================================================
# CONTACT TIMELINE API (Enterprise Grade)
# ============================================================================

@contacts_bp.route('/api/contacts/<int:contact_id>/timeline', methods=['GET'])
@login_required
def get_contact_timeline(contact_id):
    """
    Get unified timeline for contact (notes + activity logs).
    Returns merged and sorted by created_at DESC.
    """
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Contact
        from models_contact_timeline import ContactNote, ContactActivityLog
        
        # Verify contact exists and belongs to workspace
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Get notes
        notes = ContactNote.query.filter_by(
            contact_id=contact_id,
            workspace_id=workspace_id
        ).order_by(ContactNote.created_at.desc()).all()
        
        # Get activity logs
        activities = ContactActivityLog.query.filter_by(
            contact_id=contact_id,
            workspace_id=workspace_id
        ).order_by(ContactActivityLog.created_at.desc()).all()
        
        # Merge and sort
        timeline = []
        timeline.extend([note.to_dict() for note in notes])
        timeline.extend([activity.to_dict() for activity in activities])
        
        # Sort by created_at descending
        timeline.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({
            'timeline': timeline,
            'total': len(timeline)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting contact timeline: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/notes', methods=['POST'])
@login_required
def create_contact_note(contact_id):
    """
    Create a new note for contact.
    Uses transaction with rollback on error.
    """
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        from models_crm import Contact
        from models_contact_timeline import ContactNote
        from models import db
        
        # Verify contact exists
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        data = request.get_json()
        if not data or not data.get('content'):
            return jsonify({'error': 'Content is required'}), 400
        
        content = data.get('content', '').strip()
        if not content:
            return jsonify({'error': 'Content cannot be empty'}), 400
        
        # Create note with transaction
        try:
            note = ContactNote(
                workspace_id=workspace_id,
                contact_id=contact_id,
                user_id=user_id,
                content=content
            )
            
            db.session.add(note)
            db.session.commit()
            
            # Return created note
            return jsonify(note.to_dict()), 201
            
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error creating note: {str(db_error)}")
            return jsonify({'error': 'Failed to create note'}), 500
        
    except Exception as e:
        logger.error(f"Error creating contact note: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/activities', methods=['POST'])
@login_required
def create_contact_activity(contact_id):
    """Create a new activity for contact"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        from models_crm import Contact
        from models_contact_timeline import ContactActivityLog
        from models import db
        import json
        
        # Verify contact exists
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        data = request.get_json()
        action_type = data.get('action_type', 'activity')
        description = data.get('description', '').strip()
        metadata = data.get('metadata', {})
        
        if not description:
            return jsonify({'error': 'Description is required'}), 400
        
        try:
            activity = ContactActivityLog(
                workspace_id=workspace_id,
                contact_id=contact_id,
                user_id=user_id,
                action_type=action_type,
                description=description,
                metadata_json=json.dumps(metadata) if metadata else None
            )
            
            db.session.add(activity)
            db.session.commit()
            
            return jsonify(activity.to_dict()), 201
            
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error creating activity: {str(db_error)}")
            return jsonify({'error': 'Failed to create activity'}), 500
        
    except Exception as e:
        logger.error(f"Error creating contact activity: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/files', methods=['GET'])
@login_required
def get_contact_files(contact_id):
    """Get files for contact"""
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Contact
        
        # Verify contact exists
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Get files from upload directory
        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        files = []

        if os.path.exists(upload_dir):
            for filename in os.listdir(upload_dir):
                filepath = os.path.join(upload_dir, filename)
                if os.path.isfile(filepath):
                    file_size = os.path.getsize(filepath)
                    file_mtime = os.path.getmtime(filepath)

                    # Hide generated timestamp prefix in UI
                    display_name = filename
                    if '_' in filename:
                        parts = filename.split('_', 1)
                        if len(parts) > 1:
                            display_name = parts[1]

                    files.append({
                        'name': display_name,
                        'stored_name': filename,
                        'download_url': f"/api/contacts/{contact_id}/files/download/{filename}",
                        'path': filepath,
                        'size': _format_file_size(file_size),
                        'uploaded_at': datetime.fromtimestamp(file_mtime).strftime('%d.%m.%Y %H:%M')
                    })

        return jsonify({
            'files': files,
            'total': len(files)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting contact files: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/contacts/files/upload', methods=['POST'])
@login_required
def upload_contact_files():
    """Upload files for contact"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        contact_id = request.form.get('contact_id')
        if not contact_id:
            return jsonify({'error': 'Contact ID is required'}), 400
        
        from models_crm import Contact
        
        # Verify contact exists
        contact = Contact.query.filter_by(
            id=int(contact_id),
            workspace_id=workspace_id
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Check if files are in request
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')

        # Validate all file sizes before saving anything
        for file in files:
            if not file.filename:
                continue
            file.stream.seek(0, os.SEEK_END)
            file_size = file.stream.tell()
            file.stream.seek(0)
            if file_size > MAX_CONTACT_FILE_SIZE:
                return jsonify({'error': f"'{file.filename}' dosyasi 50MB sinirini asiyor"}), 413
        
        from models import db
        from models_contact_timeline import ContactActivityLog

        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        os.makedirs(upload_dir, exist_ok=True)

        uploaded_files = []
        for file in files:
            if not file.filename:
                continue

            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{filename}"
            filepath = os.path.join(upload_dir, unique_filename)

            file.save(filepath)
            file_size = os.path.getsize(filepath)

            uploaded_files.append({
                'name': filename,
                'stored_name': unique_filename,
                'path': filepath,
                'size': _format_file_size(file_size),
                'uploaded_at': datetime.now().strftime('%d.%m.%Y %H:%M')
            })

        if not uploaded_files:
            return jsonify({'error': 'No valid files to upload'}), 400

        try:
            activity = ContactActivityLog(
                workspace_id=workspace_id,
                contact_id=int(contact_id),
                user_id=user_id,
                action_type='file_upload',
                description=f'{len(uploaded_files)} dosya yüklendi',
                metadata_json=json.dumps({'files': [f['name'] for f in uploaded_files]})
            )
            db.session.add(activity)
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error while creating file upload activity: {str(db_error)}")
            return jsonify({'error': 'Files uploaded but activity log creation failed'}), 500

        return jsonify({
            'uploaded': len(uploaded_files),
            'files': uploaded_files,
            'message': f'{len(uploaded_files)} files uploaded successfully'
        }), 200
        
    except Exception as e:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        logger.error(f"Error uploading files: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/files', methods=['DELETE'])
@login_required
def delete_contact_file(contact_id):
    """Delete a file for contact"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')

        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        from models_crm import Contact
        from models import db
        from models_contact_timeline import ContactActivityLog
        import json

        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id
        ).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404

        payload = request.get_json(silent=True) or {}
        stored_name = (payload.get('stored_name') or '').strip()
        if not stored_name:
            return jsonify({'error': 'stored_name zorunludur'}), 400

        if os.path.basename(stored_name) != stored_name:
            return jsonify({'error': 'Gecersiz dosya adi'}), 400

        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        file_path = os.path.join(upload_dir, stored_name)
        if not os.path.isfile(file_path):
            return jsonify({'error': 'Dosya bulunamadi'}), 404

        display_name = stored_name.split('_', 1)[1] if '_' in stored_name else stored_name
        os.remove(file_path)

        activity = ContactActivityLog(
            workspace_id=workspace_id,
            contact_id=contact_id,
            user_id=user_id,
            action_type='file_delete',
            description='1 dosya silindi',
            metadata_json=json.dumps({'file': display_name})
        )
        db.session.add(activity)
        try:
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error while creating file delete activity: {str(db_error)}")
            return jsonify({'error': 'Dosya silindi ancak aktivite kaydi olusturulamadi'}), 500

        return jsonify({'status': 'deleted', 'file': display_name}), 200

    except Exception as e:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        logger.error(f"Error deleting contact file: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/files/download/<path:stored_name>', methods=['GET'])
@login_required
def download_contact_file(contact_id, stored_name):
    """Download a file belonging to a contact in current workspace."""
    try:
        workspace_id = session.get('workspace_id')
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400

        if os.path.basename(stored_name) != stored_name:
            return jsonify({'error': 'Gecersiz dosya adi'}), 400

        from models_crm import Contact
        contact = Contact.query.filter_by(id=contact_id, workspace_id=workspace_id).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404

        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        file_path = os.path.join(upload_dir, stored_name)
        if not os.path.isfile(file_path):
            return jsonify({'error': 'Dosya bulunamadi'}), 404

        display_name = stored_name.split('_', 1)[1] if '_' in stored_name else stored_name
        return send_from_directory(upload_dir, stored_name, as_attachment=True, download_name=display_name)

    except Exception as e:
        logger.error(f"Error downloading contact file: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/contacts/<int:contact_id>/files/share-to-chat', methods=['POST'])
@login_required
def share_contact_file_to_chat(contact_id):
    """Share a contact file into the linked Telegram chat conversation."""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        payload = request.get_json(silent=True) or {}
        stored_name = (payload.get('stored_name') or '').strip()
        caption = (payload.get('caption') or '').strip()
        channel = (payload.get('channel') or 'telegram').strip().lower()

        if channel != 'telegram':
            return jsonify({'error': 'Su anda sadece Telegram destekleniyor'}), 400

        if not stored_name:
            return jsonify({'error': 'stored_name zorunludur'}), 400
        if os.path.basename(stored_name) != stored_name:
            return jsonify({'error': 'Gecersiz dosya adi'}), 400

        from models_crm import Contact
        from models import db, Workspace
        from services.conversation_manager import ConversationManager
        from services.message_manager import MessageManager
        from services.telegram_service import TelegramService
        from realtime import emit_chat_message_event

        contact = Contact.query.filter_by(id=contact_id, workspace_id=workspace_id).first()
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        if not contact.customer_id:
            return jsonify({'error': 'Bu kisiye bagli aktif chat bulunamadi'}), 400

        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        source_path = os.path.join(upload_dir, stored_name)
        if not os.path.isfile(source_path):
            return jsonify({'error': 'Dosya bulunamadi'}), 404

        display_name = stored_name.split('_', 1)[1] if '_' in stored_name else stored_name

        conversation = ConversationManager.get_or_create_conversation(workspace_id, contact.customer_id)
        workspace = Workspace.query.get(workspace_id)
        if not workspace or not workspace.telegram_bot_token:
            return jsonify({'error': 'Telegram kanali yapilandirilmamis'}), 400

        telegram_chat_id = contact.telegram_chat_id
        if not telegram_chat_id and conversation.customer:
            telegram_chat_id = conversation.customer.telegram_chat_id
        if not telegram_chat_id:
            return jsonify({'error': 'Bu kisi icin telegram_chat_id bulunamadi'}), 400

        media_root = os.path.abspath(os.path.join('uploads', f'workspace_{workspace_id}'))
        os.makedirs(media_root, exist_ok=True)

        safe_original = secure_filename(display_name) or 'document.pdf'
        safe_name = secure_filename(f"{time.time_ns()}_{contact_id}_{safe_original}")[:220]
        if not safe_name:
            safe_name = f"{time.time_ns()}_{contact_id}_document.pdf"

        shared_path = os.path.join(media_root, safe_name)
        shutil.copy2(source_path, shared_path)

        relative_path = f"workspace_{workspace_id}/{safe_name}"
        telegram_service = TelegramService(workspace.telegram_bot_token)
        result = telegram_service.send_document(
            chat_id=telegram_chat_id,
            file_path=shared_path,
            caption=caption or None,
            filename=display_name,
        )

        if not result.get('success'):
            try:
                if os.path.exists(shared_path):
                    os.remove(shared_path)
            except Exception:
                pass
            return jsonify({'error': result.get('error', 'Dosya Telegram sohbetinde paylasilamadi')}), 500

        body_label = f"[📄 Telegram Belge] {display_name}"
        if caption:
            body_label += f" - {caption}"

        try:
            message = MessageManager.save_outgoing_message(
                conversation_id=conversation.id,
                message_body=body_label,
                sender_id=user_id,
                meta_message_id=result.get('message_id'),
                channel='telegram',
                media_type='document',
                media_url=relative_path,
            )
            message.is_read = True
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error while saving shared file message: {str(db_error)}")
            return jsonify({'error': 'Dosya gonderildi ancak chat kaydi olusturulamadi'}), 500

        try:
            ConversationManager.update_last_message_time(conversation.id)
        except Exception as conv_error:
            logger.warning(f"Conversation timestamp update warning: {str(conv_error)}")

        try:
            emit_chat_message_event(message.id, workspace_id=workspace_id)
        except Exception as emit_error:
            logger.warning(f"Realtime emit warning: {str(emit_error)}")

        return jsonify({
            'status': 'sent',
            'channel': 'telegram',
            'conversation_id': conversation.id,
            'message_id': message.id,
            'message': {
                'id': message.id,
                'conversation_id': conversation.id,
                'message_body': message.message_body,
                'media_type': message.media_type,
                'media_url': f"/api/media/{message.media_url}",
                'created_at': message.created_at.isoformat(),
            },
        }), 200

    except Exception as e:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        logger.error(f"Error sharing contact file to chat: {str(e)}")
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


@contacts_bp.route('/api/v1/contacts/<int:contact_id>', methods=['DELETE'])
@login_required
def delete_contact(contact_id):
    """Delete a contact"""
    try:
        workspace_id = session.get('workspace_id')
        
        if not workspace_id:
            return jsonify({'error': 'Workspace not found'}), 400
        
        from models_crm import Contact
        from models import db
        
        contact = Contact.query.filter_by(
            id=contact_id,
            workspace_id=workspace_id
        ).first()
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Delete the contact
        db.session.delete(contact)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Contact deleted'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting contact: {str(e)}")
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


@contacts_bp.route('/api/v1/user-preferences/contacts-column-widths', methods=['GET'])
@login_required
def get_contacts_column_widths():
    """Get user's column width preferences for contacts table"""
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not user_id or not workspace_id:
            return jsonify({'error': 'User or workspace not found'}), 400
        
        from models import db
        from sqlalchemy import text
        
        result = db.session.execute(
            text("SELECT preference_value FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_column_widths'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            import json
            return jsonify({'widths': json.loads(result[0])}), 200
        
        return jsonify({'widths': {}}), 200
        
    except Exception as e:
        logger.error(f"Error getting column widths: {str(e)}")
        return jsonify({'widths': {}}), 200


@contacts_bp.route('/api/v1/user-preferences/contacts-column-widths', methods=['POST'])
@login_required
def save_contacts_column_widths():
    """Save user's column width preferences for contacts table"""
    try:
        user_id = session.get('user_id')
        workspace_id = session.get('workspace_id')
        
        if not user_id or not workspace_id:
            return jsonify({'error': 'User or workspace not found'}), 400
        
        data = request.get_json()
        if not data or 'widths' not in data:
            return jsonify({'error': 'No widths provided'}), 400
        
        widths = data['widths']
        
        from models import db
        from sqlalchemy import text
        import json
        
        # Check if preference exists
        result = db.session.execute(
            text("SELECT id FROM user_preferences WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_column_widths'"),
            {'user_id': user_id, 'workspace_id': workspace_id}
        ).fetchone()
        
        if result:
            # Update existing
            db.session.execute(
                text("UPDATE user_preferences SET preference_value = :value, updated_at = CURRENT_TIMESTAMP WHERE user_id = :user_id AND workspace_id = :workspace_id AND preference_key = 'contacts_column_widths'"),
                {'value': json.dumps(widths), 'user_id': user_id, 'workspace_id': workspace_id}
            )
        else:
            # Insert new
            db.session.execute(
                text("INSERT INTO user_preferences (user_id, workspace_id, preference_key, preference_value, created_at, updated_at) VALUES (:user_id, :workspace_id, 'contacts_column_widths', :value, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                {'user_id': user_id, 'workspace_id': workspace_id, 'value': json.dumps(widths)}
            )
        
        db.session.commit()
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        logger.error(f"Error saving column widths: {str(e)}")
        return jsonify({'error': str(e)}), 500
