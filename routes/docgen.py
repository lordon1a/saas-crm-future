"""
DocGen Blueprint - Document Generation Routes
Handles template management and document generation for CRM records
"""

import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, abort, session
from werkzeug.utils import secure_filename
from functools import wraps

from models import db
from models_crm import DocTemplate, GeneratedDocument
from services.docgen_engine import generate_document, UPLOAD_FOLDER
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('docgen', __name__, url_prefix='/api/docgen')

ALLOWED_EXTENSIONS = {'docx', 'pptx', 'html'}


def login_required_api(f):
    """Decorator to require authentication for API endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Unauthorized'}), 401
        if not session.get('workspace_id'):
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _build_nested_context(workspace_id, user_id, record_type, record_id):
    """
    Build nested context dict for template rendering.
    Fetches related CRM records from database.
    
    Returns dict with structure:
    {
        'deal': {...},
        'contact': {...},
        'company': {...},
        'user': {...},
        'workspace': {...},
        'today': '2024-03-23'
    }
    """
    from models_crm import Deal, Contact, Company
    from models import User, Workspace
    
    context = {
        'today': datetime.utcnow().strftime('%Y-%m-%d'),
        'user': {},
        'workspace': {},
        'deal': {},
        'contact': {},
        'company': {}
    }
    
    # Fetch user info
    user = User.query.get(user_id)
    if user:
        context['user'] = {
            'id': user.id,
            'name': user.name,
            'email': user.email or ''
        }
    
    # Fetch workspace info
    workspace = Workspace.query.get(workspace_id)
    if workspace:
        context['workspace'] = {
            'id': workspace.id,
            'name': workspace.company_name
        }
    
    # Fetch primary record based on record_type
    if record_type == 'deal':
        deal = Deal.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if deal:
            context['deal'] = {
                'id': deal.id,
                'name': deal.name,
                'value': float(deal.value) if deal.value else 0,
                'description': deal.next_step or '',
                'status': deal.status,
                'created_at': deal.created_at.strftime('%Y-%m-%d') if deal.created_at else ''
            }
            
            # Fetch related contact
            if deal.contact_id:
                contact = Contact.query.filter_by(id=deal.contact_id, workspace_id=workspace_id).first()
                if contact:
                    context['contact'] = {
                        'id': contact.id,
                        'name': contact.full_name,
                        'email': contact.email or '',
                        'phone': contact.phone or '',
                        'job_title': contact.job_title or ''
                    }
            
            # Fetch related company
            if deal.company_id:
                company = Company.query.filter_by(id=deal.company_id, workspace_id=workspace_id).first()
                if company:
                    context['company'] = {
                        'id': company.id,
                        'name': company.name,
                        'industry': company.industry or '',
                        'website': company.website or '',
                        'phone': company.phone or '',
                        'address': company.address or ''
                    }
    
    elif record_type == 'contact':
        contact = Contact.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if contact:
            context['contact'] = {
                'id': contact.id,
                'name': contact.full_name,
                'email': contact.email or '',
                'phone': contact.phone or '',
                'job_title': contact.job_title or ''
            }
            
            # Fetch related company
            if contact.company_id:
                company = Company.query.filter_by(id=contact.company_id, workspace_id=workspace_id).first()
                if company:
                    context['company'] = {
                        'id': company.id,
                        'name': company.name,
                        'industry': company.industry or '',
                        'website': company.website or '',
                        'phone': company.phone or '',
                        'address': company.address or ''
                    }
    
    elif record_type == 'company':
        company = Company.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if company:
            context['company'] = {
                'id': company.id,
                'name': company.name,
                'industry': company.industry or '',
                'website': company.website or '',
                'phone': company.phone or '',
                'address': company.address or ''
            }
    
    elif record_type == 'quote':
        from models_crm import Quote
        quote = Quote.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if quote:
            context['quote'] = {
                'id': quote.id,
                'quote_number': quote.quote_number,
                'status': quote.status,
                'grand_total': float(quote.grand_total) if quote.grand_total else 0,
                'currency': quote.currency,
                'valid_until': quote.valid_until.strftime('%Y-%m-%d') if quote.valid_until else ''
            }
            
            # Fetch related deal
            if quote.deal_id:
                deal = Deal.query.filter_by(id=quote.deal_id, workspace_id=workspace_id).first()
                if deal:
                    context['deal'] = {
                        'id': deal.id,
                        'name': deal.name,
                        'value': float(deal.value) if deal.value else 0,
                        'description': deal.next_step or ''
                    }
                    
                    # Fetch contact and company from deal
                    if deal.contact_id:
                        contact = Contact.query.filter_by(id=deal.contact_id, workspace_id=workspace_id).first()
                        if contact:
                            context['contact'] = {
                                'id': contact.id,
                                'name': contact.full_name,
                                'email': contact.email or '',
                                'phone': contact.phone or ''
                            }
                    
                    if deal.company_id:
                        company = Company.query.filter_by(id=deal.company_id, workspace_id=workspace_id).first()
                        if company:
                            context['company'] = {
                                'id': company.id,
                                'name': company.name,
                                'website': company.website or '',
                                'phone': company.phone or ''
                            }
    
    elif record_type == 'task':
        from models_automation import Task
        task = Task.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if task:
            context['task'] = {
                'id': task.id,
                'title': task.title,
                'description': task.description or '',
                'status': task.status,
                'due_date': task.due_date.strftime('%Y-%m-%d') if task.due_date else ''
            }
            
            # Fetch related deal if exists
            if hasattr(task, 'deal_id') and task.deal_id:
                deal = Deal.query.filter_by(id=task.deal_id, workspace_id=workspace_id).first()
                if deal:
                    context['deal'] = {
                        'id': deal.id,
                        'name': deal.name,
                        'value': float(deal.value) if deal.value else 0
                    }
    
    elif record_type == 'product':
        from models_crm import Product
        product = Product.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if product:
            context['product'] = {
                'id': product.id,
                'name': product.name,
                'sku': product.sku or '',
                'description': product.description or '',
                'unit_price': float(product.unit_price) if product.unit_price else 0,
                'currency': product.currency
            }
    
    return context


# ═══ TEMPLATE MANAGER ═══

@bp.route('/templates', methods=['GET'])
@login_required_api
def list_templates():
    """List all active templates for current workspace, optionally filtered by object_type."""
    workspace_id = session.get('workspace_id')
    object_type = request.args.get('object_type')
    
    query = DocTemplate.query.filter_by(workspace_id=workspace_id, is_active=True)
    if object_type:
        query = query.filter_by(object_type=object_type)
    
    templates = query.order_by(DocTemplate.created_at.desc()).all()
    return jsonify({'templates': [t.to_dict() for t in templates]})


@bp.route('/templates', methods=['POST'])
@login_required_api
def create_template():
    """
    Upload a new template.
    Form data: name, description, object_type, field_map (JSON string)
    File: template file (.docx / .pptx / .html)
    """
    workspace_id = session.get('workspace_id')
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file or not _allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed: docx, pptx, html'}), 400

    filename = secure_filename(file.filename)
    # Add workspace_id to filename to avoid conflicts
    filename = f"ws{workspace_id}_{filename}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    file_type = filename.rsplit('.', 1)[1].lower()

    field_map_raw = request.form.get('field_map')
    field_map = json.loads(field_map_raw) if field_map_raw else None

    try:
        template = DocTemplate(
            workspace_id=workspace_id,
            name=request.form.get('name', filename),
            description=request.form.get('description', ''),
            file_path=file_path,
            file_type=file_type,
            object_type=request.form.get('object_type'),
            field_map=field_map,
        )
        db.session.add(template)
        db.session.commit()
        return jsonify(template.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating template: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/templates/<int:template_id>', methods=['PUT'])
@login_required_api
def update_template(template_id):
    """Update template metadata (not the file itself)."""
    workspace_id = session.get('workspace_id')
    template = DocTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first()
    
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    
    data = request.get_json()

    try:
        for field in ('name', 'description', 'object_type', 'field_map', 'is_active'):
            if field in data:
                setattr(template, field, data[field])

        template.version += 1
        template.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify(template.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating template: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/templates/<int:template_id>', methods=['DELETE'])
@login_required_api
def delete_template(template_id):
    """Soft-delete a template."""
    workspace_id = session.get('workspace_id')
    template = DocTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first()
    
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    
    try:
        template.is_active = False
        db.session.commit()
        return jsonify({'message': 'Template deactivated'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting template: {e}")
        return jsonify({'error': str(e)}), 500


# ═══ DOCUMENT GENERATION ═══

@bp.route('/generate', methods=['POST'])
@login_required_api
def generate():
    """
    Generate a document for a single CRM record.
    Body: { template_id, record_id, record_type, record_data, output_type }
    record_data: dict of the CRM record's fields
    output_type: 'pdf' | 'docx' | 'pptx' (optional, defaults to template's type)
    """
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    template_id = data.get('template_id')
    record_id = data.get('record_id')
    record_type = data.get('record_type', '')
    output_type = data.get('output_type')

    if not template_id or not record_id or not record_type:
        return jsonify({'error': 'template_id, record_id, and record_type are required'}), 400

    template = DocTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first()
    if not template:
        return jsonify({'error': 'Template not found'}), 404

    doc = None
    try:
        # Build nested context from CRM records
        context = _build_nested_context(workspace_id, user_id, record_type, record_id)
        
        doc = GeneratedDocument(
            workspace_id=workspace_id,
            template_id=template_id,
            record_id=record_id,
            record_type=record_type,
            output_type=output_type or template.file_type,
            status='processing',
        )
        db.session.add(doc)
        db.session.commit()

        output_path = generate_document(template, context, output_type)
        doc.output_path = output_path
        doc.status = 'done'
        doc.completed_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'document': doc.to_dict()}), 201
        
    except Exception as e:
        db.session.rollback()
        if doc:
            doc.status = 'error'
            doc.error_msg = str(e)
            db.session.commit()
        logger.error(f"Error generating document: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/generate/bulk', methods=['POST'])
@login_required_api
def generate_bulk():
    """
    Queue bulk generation for multiple records.
    Body: { template_id, records: [{id, record_type}], output_type }
    """
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    template_id = data.get('template_id')
    records = data.get('records', [])
    output_type = data.get('output_type')

    if not template_id or not records:
        return jsonify({'error': 'template_id and records are required'}), 400

    template = DocTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first()
    if not template:
        return jsonify({'error': 'Template not found'}), 404

    created_docs = []
    
    try:
        for rec in records:
            record_id = rec.get('id')
            record_type = rec.get('record_type', '')
            
            if not record_id or not record_type:
                continue
            
            # Build nested context from CRM records
            context = _build_nested_context(workspace_id, user_id, record_type, record_id)
            
            doc = GeneratedDocument(
                workspace_id=workspace_id,
                template_id=template_id,
                record_id=record_id,
                record_type=record_type,
                output_type=output_type or template.file_type,
                status='processing',
            )
            db.session.add(doc)
            db.session.flush()

            try:
                output_path = generate_document(template, context, output_type)
                doc.output_path = output_path
                doc.status = 'done'
                doc.completed_at = datetime.utcnow()
            except Exception as e:
                doc.status = 'error'
                doc.error_msg = str(e)
                logger.error(f"Error generating document for record {record_id}: {e}")

            created_docs.append(doc.to_dict())

        db.session.commit()
        return jsonify({'queued': len(created_docs), 'documents': created_docs}), 202
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in bulk generation: {e}")
        return jsonify({'error': str(e)}), 500


# ═══ DOWNLOAD + STATUS ═══

@bp.route('/download/<int:doc_id>', methods=['GET'])
@login_required_api
def download(doc_id):
    """Download a generated document."""
    workspace_id = session.get('workspace_id')
    doc = GeneratedDocument.query.filter_by(id=doc_id, workspace_id=workspace_id).first()
    
    if not doc:
        abort(404, description='Document not found')
    
    if doc.status != 'done' or not doc.output_path:
        abort(404, description='Document not ready or not found')
    
    if not os.path.exists(doc.output_path):
        abort(404, description='Document file not found on disk')
    
    return send_file(doc.output_path, as_attachment=True)


@bp.route('/documents', methods=['GET'])
@login_required_api
def list_documents():
    """List generated documents for current workspace, filterable by record_id or record_type."""
    workspace_id = session.get('workspace_id')
    record_id = request.args.get('record_id', type=int)
    record_type = request.args.get('record_type')
    status = request.args.get('status')
    limit = request.args.get('limit', 50, type=int)

    query = GeneratedDocument.query.filter_by(workspace_id=workspace_id)
    
    if record_id:
        query = query.filter_by(record_id=record_id)
    if record_type:
        query = query.filter_by(record_type=record_type)
    if status:
        query = query.filter_by(status=status)

    docs = query.order_by(GeneratedDocument.created_at.desc()).limit(limit).all()
    return jsonify([d.to_dict() for d in docs])


@bp.route('/documents/<int:doc_id>/status', methods=['GET'])
@login_required_api
def doc_status(doc_id):
    """Poll the status of a single document."""
    workspace_id = session.get('workspace_id')
    doc = GeneratedDocument.query.filter_by(id=doc_id, workspace_id=workspace_id).first()
    
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    
    return jsonify(doc.to_dict())
