"""
DocGen Blueprint - Document Generation Routes
Handles template management and document generation for CRM records
"""

import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, abort, session, render_template, redirect, url_for
from werkzeug.utils import secure_filename
from functools import wraps

from models import db
from models_crm import DocTemplate, GeneratedDocument
from services.docgen_engine import generate_document, UPLOAD_FOLDER
from utils.app_guard import require_app
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('docgen', __name__)

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
        # Add top-level user fields for easier access
        context['current_user_name'] = user.name
        context['current_user_email'] = user.email or ''
    
    # Fetch workspace info
    workspace = Workspace.query.get(workspace_id)
    if workspace:
        context['workspace'] = {
            'id': workspace.id,
            'name': workspace.company_name,
            'company_name': workspace.company_name,
            'email': workspace.email or ''
        }
        # Add top-level workspace fields for easier access
        context['workspace_name'] = workspace.company_name
        context['workspace_email'] = workspace.email or ''
    
    # Fetch primary record based on record_type
    if record_type == 'deal':
        deal = Deal.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if deal:
            context['deal'] = {
                'id': deal.id,
                'name': deal.name,
                'value': float(deal.value) if deal.value else 0,
                'value_formatted': f"{float(deal.value):,.2f}" if deal.value else "0.00",
                'currency': 'TRY',
                'status': deal.status,
                'revenue_type': deal.revenue_type or 'one_time',
                'mrr': float(deal.mrr) if deal.mrr else 0,
                'arr': float(deal.arr) if deal.arr else 0,
                'forecast_category': deal.forecast_category or 'pipeline',
                'churn_risk': deal.churn_risk or 'low',
                'next_step': deal.next_step or '',
                'expected_close_date': deal.expected_close_date.strftime('%Y-%m-%d') if deal.expected_close_date else '',
                'renewal_date': deal.renewal_date.strftime('%Y-%m-%d') if deal.renewal_date else '',
                'created_at': deal.created_at.strftime('%Y-%m-%d') if deal.created_at else '',
                'updated_at': deal.updated_at.strftime('%Y-%m-%d') if deal.updated_at else '',
                'closed_at': deal.closed_at.strftime('%Y-%m-%d') if deal.closed_at else '',
                'stage_entered_at': deal.stage_entered_at.strftime('%Y-%m-%d') if deal.stage_entered_at else '',
                'days_in_stage': deal.days_in_current_stage() if hasattr(deal, 'days_in_current_stage') else 0,
                'is_rotting': deal.is_rotting() if hasattr(deal, 'is_rotting') else False,
                'weighted_value': deal.get_weighted_value() if hasattr(deal, 'get_weighted_value') else 0,
                'win_loss_reason': deal.win_loss_reason or '',
                'validity_days': 30  # Default validity period for quotes
            }
            
            # Add stage info
            if deal.stage:
                context['deal']['stage_name'] = deal.stage.name
                context['deal']['stage_probability'] = deal.stage.probability
                context['deal']['stage_order'] = deal.stage.order
            
            # Add pipeline info
            if deal.pipeline:
                context['deal']['pipeline_name'] = deal.pipeline.name
            
            # Fetch related contact
            if deal.contact_id:
                contact = Contact.query.filter_by(id=deal.contact_id, workspace_id=workspace_id).first()
                if contact:
                    context['contact'] = {
                        'id': contact.id,
                        'name': contact.full_name,
                        'full_name': contact.full_name,
                        'first_name': contact.first_name,
                        'last_name': contact.last_name or '',
                        'email': contact.email or '',
                        'phone': contact.phone or '',
                        'whatsapp_phone': contact.whatsapp_phone or '',
                        'telegram_chat_id': contact.telegram_chat_id or '',
                        'job_title': contact.job_title or '',
                        'role': contact.role or '',
                        'lead_score': contact.lead_score or 0,
                        'lead_source': contact.lead_source or '',
                        'lifecycle_stage': contact.lifecycle_stage or 'lead',
                        'is_starred': contact.is_starred or False,
                        'created_at': contact.created_at.strftime('%Y-%m-%d') if contact.created_at else '',
                        'qualified_at': contact.qualified_at.strftime('%Y-%m-%d') if contact.qualified_at else '',
                        'converted_at': contact.converted_at.strftime('%Y-%m-%d') if contact.converted_at else ''
                    }
            
            # Fetch related company
            if deal.company_id:
                company = Company.query.filter_by(id=deal.company_id, workspace_id=workspace_id).first()
                if company:
                    context['company'] = {
                        'id': company.id,
                        'name': company.name,
                        'industry': company.industry or '',
                        'size': company.size or '',
                        'website': company.website or '',
                        'phone': company.phone or '',
                        'address': company.address or '',
                        'created_at': company.created_at.strftime('%Y-%m-%d') if company.created_at else '',
                        'updated_at': company.updated_at.strftime('%Y-%m-%d') if company.updated_at else ''
                    }
    
    elif record_type == 'contact':
        contact = Contact.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if contact:
            context['contact'] = {
                'id': contact.id,
                'name': contact.full_name,
                'first_name': contact.first_name,
                'last_name': contact.last_name or '',
                'email': contact.email or '',
                'phone': contact.phone or '',
                'whatsapp_phone': contact.whatsapp_phone or '',
                'telegram_chat_id': contact.telegram_chat_id or '',
                'job_title': contact.job_title or '',
                'role': contact.role or '',
                'lead_score': contact.lead_score or 0,
                'lead_source': contact.lead_source or '',
                'lifecycle_stage': contact.lifecycle_stage or 'lead',
                'is_starred': contact.is_starred or False,
                'created_at': contact.created_at.strftime('%Y-%m-%d') if contact.created_at else '',
                'updated_at': contact.updated_at.strftime('%Y-%m-%d') if contact.updated_at else '',
                'qualified_at': contact.qualified_at.strftime('%Y-%m-%d') if contact.qualified_at else '',
                'converted_at': contact.converted_at.strftime('%Y-%m-%d') if contact.converted_at else '',
                'last_activity_at': contact.last_activity_at.strftime('%Y-%m-%d') if contact.last_activity_at else ''
            }
            
            # Fetch related company
            if contact.company_id:
                company = Company.query.filter_by(id=contact.company_id, workspace_id=workspace_id).first()
                if company:
                    context['company'] = {
                        'id': company.id,
                        'name': company.name,
                        'industry': company.industry or '',
                        'size': company.size or '',
                        'website': company.website or '',
                        'phone': company.phone or '',
                        'address': company.address or '',
                        'created_at': company.created_at.strftime('%Y-%m-%d') if company.created_at else '',
                        'updated_at': company.updated_at.strftime('%Y-%m-%d') if company.updated_at else ''
                    }
    
    elif record_type == 'company':
        company = Company.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if company:
            context['company'] = {
                'id': company.id,
                'name': company.name,
                'industry': company.industry or '',
                'size': company.size or '',
                'website': company.website or '',
                'phone': company.phone or '',
                'address': company.address or '',
                'created_at': company.created_at.strftime('%Y-%m-%d') if company.created_at else '',
                'updated_at': company.updated_at.strftime('%Y-%m-%d') if company.updated_at else ''
            }
    
    elif record_type == 'quote':
        from models_crm import Quote
        quote = Quote.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if quote:
            context['quote'] = {
                'id': quote.id,
                'quote_number': quote.quote_number,
                'status': quote.status,
                'currency': quote.currency,
                'subtotal': float(quote.subtotal) if quote.subtotal else 0,
                'subtotal_formatted': f"{float(quote.subtotal):,.2f}" if quote.subtotal else "0.00",
                'discount_total': float(quote.discount_total) if quote.discount_total else 0,
                'discount_total_formatted': f"{float(quote.discount_total):,.2f}" if quote.discount_total else "0.00",
                'tax_total': float(quote.tax_total) if quote.tax_total else 0,
                'tax_total_formatted': f"{float(quote.tax_total):,.2f}" if quote.tax_total else "0.00",
                'grand_total': float(quote.grand_total) if quote.grand_total else 0,
                'grand_total_formatted': f"{float(quote.grand_total):,.2f}" if quote.grand_total else "0.00",
                'notes': quote.notes or '',
                'valid_until': quote.valid_until.strftime('%Y-%m-%d') if quote.valid_until else '',
                'created_at': quote.created_at.strftime('%Y-%m-%d') if quote.created_at else '',
                'updated_at': quote.updated_at.strftime('%Y-%m-%d') if quote.updated_at else ''
            }
            
            # Fetch related deal
            if quote.deal_id:
                deal = Deal.query.filter_by(id=quote.deal_id, workspace_id=workspace_id).first()
                if deal:
                    context['deal'] = {
                        'id': deal.id,
                        'name': deal.name,
                        'value': float(deal.value) if deal.value else 0,
                        'value_formatted': f"{float(deal.value):,.2f}" if deal.value else "0.00",
                        'status': deal.status,
                        'next_step': deal.next_step or ''
                    }
                    
                    # Fetch contact and company from deal
                    if deal.contact_id:
                        contact = Contact.query.filter_by(id=deal.contact_id, workspace_id=workspace_id).first()
                        if contact:
                            context['contact'] = {
                                'id': contact.id,
                                'name': contact.full_name,
                                'first_name': contact.first_name,
                                'last_name': contact.last_name or '',
                                'email': contact.email or '',
                                'phone': contact.phone or '',
                                'job_title': contact.job_title or ''
                            }
                    
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
    
    elif record_type == 'task':
        from models_automation import Task
        task = Task.query.filter_by(id=record_id, workspace_id=workspace_id).first()
        if task:
            context['task'] = {
                'id': task.id,
                'title': task.title,
                'description': task.description or '',
                'status': task.status,
                'priority': task.priority or 'medium',
                'due_date': task.due_date.strftime('%Y-%m-%d') if task.due_date else '',
                'completed_at': task.completed_at.strftime('%Y-%m-%d') if task.completed_at else '',
                'created_at': task.created_at.strftime('%Y-%m-%d') if task.created_at else '',
                'updated_at': task.updated_at.strftime('%Y-%m-%d') if task.updated_at else ''
            }
            
            # Fetch related deal if exists
            if hasattr(task, 'deal_id') and task.deal_id:
                deal = Deal.query.filter_by(id=task.deal_id, workspace_id=workspace_id).first()
                if deal:
                    context['deal'] = {
                        'id': deal.id,
                        'name': deal.name,
                        'value': float(deal.value) if deal.value else 0,
                        'value_formatted': f"{float(deal.value):,.2f}" if deal.value else "0.00",
                        'status': deal.status
                    }
            
            # Fetch related contact if exists
            if hasattr(task, 'contact_id') and task.contact_id:
                contact = Contact.query.filter_by(id=task.contact_id, workspace_id=workspace_id).first()
                if contact:
                    context['contact'] = {
                        'id': contact.id,
                        'name': contact.full_name,
                        'email': contact.email or '',
                        'phone': contact.phone or ''
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
                'unit_price_formatted': f"{float(product.unit_price):,.2f}" if product.unit_price else "0.00",
                'currency': product.currency,
                'is_active': product.is_active,
                'created_at': product.created_at.strftime('%Y-%m-%d') if product.created_at else '',
                'updated_at': product.updated_at.strftime('%Y-%m-%d') if product.updated_at else ''
            }
    
    return context


# ═══ TEMPLATE MANAGER ═══

@bp.route('/templates', methods=['GET'])
@login_required_api
@require_app('docgen')
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
@require_app('docgen')
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
@require_app('docgen')
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
@require_app('docgen')
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
@require_app('docgen')
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
@require_app('docgen')
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


@bp.route('/bulk-generate', methods=['POST'])
@login_required_api
@require_app('docgen')
def bulk_generate_with_criteria():
    """
    Bulk generation with filter criteria (for Pipeline page).
    Body: { template_id, entity_type, output_format, criteria: {filter_type, stage_id?, start_date?, end_date?} }
    """
    workspace_id = session.get('workspace_id')
    user_id = session.get('user_id')
    data = request.get_json()
    
    template_id = data.get('template_id')
    entity_type = data.get('entity_type', 'deal')
    output_format = data.get('output_format', 'docx')
    criteria = data.get('criteria', {})
    
    if not template_id:
        return jsonify({'error': 'template_id is required'}), 400
    
    template = DocTemplate.query.filter_by(id=template_id, workspace_id=workspace_id).first()
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    
    # Build query based on criteria
    from models_crm import Deal
    query = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False)
    
    filter_type = criteria.get('filter_type', 'won')
    
    if filter_type == 'won':
        query = query.filter_by(status='won')
    elif filter_type == 'stage':
        stage_id = criteria.get('stage_id')
        if not stage_id:
            return jsonify({'error': 'stage_id required for stage filter'}), 400
        query = query.filter_by(stage_id=stage_id)
    elif filter_type == 'date':
        start_date = criteria.get('start_date')
        end_date = criteria.get('end_date')
        if not start_date or not end_date:
            return jsonify({'error': 'start_date and end_date required for date filter'}), 400
        query = query.filter(Deal.created_at >= start_date, Deal.created_at <= end_date)
    
    deals = query.all()
    
    if not deals:
        return jsonify({'error': 'No deals found matching criteria', 'success_count': 0}), 404
    
    created_docs = []
    success_count = 0
    
    try:
        for deal in deals:
            # Build nested context from CRM records
            context = _build_nested_context(workspace_id, user_id, entity_type, deal.id)
            
            doc = GeneratedDocument(
                workspace_id=workspace_id,
                template_id=template_id,
                record_id=deal.id,
                record_type=entity_type,
                output_type=output_format,
                status='processing',
            )
            db.session.add(doc)
            db.session.flush()

            try:
                output_path = generate_document(template, context, output_format)
                doc.output_path = output_path
                doc.status = 'done'
                doc.completed_at = datetime.utcnow()
                success_count += 1
                created_docs.append({
                    'id': doc.id,
                    'filename': os.path.basename(output_path),
                    'download_url': f'/api/docgen/download/{doc.id}'
                })
            except Exception as e:
                doc.status = 'error'
                doc.error_msg = str(e)
                logger.error(f"Error generating document for deal {deal.id}: {e}")

        db.session.commit()
        return jsonify({
            'success_count': success_count,
            'total_count': len(deals),
            'documents': created_docs
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in bulk generation: {e}")
        return jsonify({'error': str(e)}), 500


# ═══ DOWNLOAD + STATUS ═══

@bp.route('/download/<int:doc_id>', methods=['GET'])
@login_required_api
@require_app('docgen')
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


@bp.route('/template-manager', methods=['GET'])
@require_app('docgen')
def docgen_templates_page():
    """Render DocGen template management page."""
    # Check authentication
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    if not session.get('workspace_id'):
        return redirect(url_for('auth.login'))
    
    return render_template('docgen_templates.html')


@bp.route('/documents', methods=['GET'])
@login_required_api
@require_app('docgen')
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
@require_app('docgen')
def doc_status(doc_id):
    """Poll the status of a single document."""
    workspace_id = session.get('workspace_id')
    doc = GeneratedDocument.query.filter_by(id=doc_id, workspace_id=workspace_id).first()
    
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    
    return jsonify(doc.to_dict())
