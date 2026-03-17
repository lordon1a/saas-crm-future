"""
Contact File Upload Routes
Handles file upload and retrieval for contacts
"""
from flask import Blueprint, request, jsonify, session
from functools import wraps
import logging
import os
from werkzeug.utils import secure_filename
from datetime import datetime

logger = logging.getLogger(__name__)

contacts_files_bp = Blueprint('contacts_files', __name__)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def _format_file_size(size_bytes):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / 1024:.2f} KB"


@contacts_files_bp.route('/api/contacts/files/upload', methods=['POST'])
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
        from models import db
        
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
        
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Validate all files before saving any of them
        for file in files:
            if not file.filename:
                continue
            file.stream.seek(0, os.SEEK_END)
            file_size = file.stream.tell()
            file.stream.seek(0)
            if file_size > MAX_FILE_SIZE:
                return jsonify({
                    'error': f"'{file.filename}' dosyasi 50MB sinirini asiyor"
                }), 413

        uploaded_files = []
        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{filename}"
                filepath = os.path.join(upload_dir, unique_filename)
                
                # Save file
                file.save(filepath)
                
                # Get file size
                file_size = os.path.getsize(filepath)
                
                uploaded_files.append({
                    'name': filename,
                    'stored_name': unique_filename,
                    'path': filepath,
                    'size': _format_file_size(file_size),
                    'uploaded_at': datetime.now().strftime('%d.%m.%Y %H:%M')
                })
        
        # Create activity log
        from models_contact_timeline import ContactActivityLog
        import json
        
        activity = ContactActivityLog(
            workspace_id=workspace_id,
            contact_id=int(contact_id),
            user_id=user_id,
            action_type='file_upload',
            description=f'{len(uploaded_files)} dosya yüklendi',
            metadata_json=json.dumps({'files': [f['name'] for f in uploaded_files]})
        )
        
        db.session.add(activity)
        try:
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error on file upload commit: {str(db_error)}")
            return jsonify({'error': 'Dosya yüklendi ancak aktivite kaydi olusturulamadi'}), 500
        
        return jsonify({
            'uploaded': len(uploaded_files),
            'files': uploaded_files,
            'message': f'{len(uploaded_files)} dosya başarıyla yüklendi'
        }), 200
        
    except Exception as e:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        logger.error(f"Error uploading files: {str(e)}")
        return jsonify({'error': str(e)}), 500


@contacts_files_bp.route('/api/contacts/<int:contact_id>/files', methods=['GET'])
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
                    
                    # Remove timestamp prefix from display name
                    display_name = filename
                    if '_' in filename:
                        parts = filename.split('_', 1)
                        if len(parts) > 1:
                            display_name = parts[1]
                    
                    files.append({
                        'name': display_name,
                        'stored_name': filename,
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


@contacts_files_bp.route('/api/contacts/<int:contact_id>/files', methods=['DELETE'])
@login_required
def delete_contact_file(contact_id):
    """Delete a file for a contact"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')

        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        from models_crm import Contact
        from models import db

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

        # Prevent path traversal and ensure deletion stays inside contact folder
        if os.path.basename(stored_name) != stored_name:
            return jsonify({'error': 'Gecersiz dosya adi'}), 400

        upload_dir = os.path.join('uploads', 'contacts', str(contact_id))
        file_path = os.path.join(upload_dir, stored_name)

        if not os.path.isfile(file_path):
            return jsonify({'error': 'Dosya bulunamadi'}), 404

        display_name = stored_name.split('_', 1)[1] if '_' in stored_name else stored_name
        os.remove(file_path)

        from models_contact_timeline import ContactActivityLog
        import json

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
            logger.error(f"Database error on file delete commit: {str(db_error)}")
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
