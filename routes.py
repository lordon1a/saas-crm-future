"""
DocGen Blueprint
Mount with: app.register_blueprint(docgen_bp, url_prefix='/docgen')
"""

import os
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename

from .models import db, DocTemplate, GeneratedDocument
from .engine import generate_document, UPLOAD_FOLDER

docgen_bp = Blueprint('docgen', __name__)

ALLOWED_EXTENSIONS = {'docx', 'pptx', 'html'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ─────────────────────────────────────────────
#  TEMPLATE MANAGER
# ─────────────────────────────────────────────

@docgen_bp.route('/templates', methods=['GET'])
def list_templates():
    """List all active templates, optionally filtered by object_type."""
    object_type = request.args.get('object_type')
    query = DocTemplate.query.filter_by(is_active=True)
    if object_type:
        query = query.filter_by(object_type=object_type)
    templates = query.order_by(DocTemplate.created_at.desc()).all()
    return jsonify([t.to_dict() for t in templates])


@docgen_bp.route('/templates', methods=['POST'])
def create_template():
    """
    Upload a new template.
    Form data: name, description, object_type, field_map (JSON string)
    File: template file (.docx / .pptx / .html)
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file or not _allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed: docx, pptx, html'}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    file_type = filename.rsplit('.', 1)[1].lower()

    import json
    field_map_raw = request.form.get('field_map')
    field_map = json.loads(field_map_raw) if field_map_raw else None

    template = DocTemplate(
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


@docgen_bp.route('/templates/<int:template_id>', methods=['PUT'])
def update_template(template_id):
    """Update template metadata (not the file itself)."""
    template = DocTemplate.query.get_or_404(template_id)
    data = request.get_json()

    for field in ('name', 'description', 'object_type', 'field_map', 'is_active'):
        if field in data:
            setattr(template, field, data[field])

    template.version += 1
    template.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(template.to_dict())


@docgen_bp.route('/templates/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    """Soft-delete a template."""
    template = DocTemplate.query.get_or_404(template_id)
    template.is_active = False
    db.session.commit()
    return jsonify({'message': 'Template deactivated'})


# ─────────────────────────────────────────────
#  DOCUMENT GENERATION
# ─────────────────────────────────────────────

@docgen_bp.route('/generate', methods=['POST'])
def generate():
    """
    Generate a document for a single CRM record.
    Body: { template_id, record_id, record_type, record_data, output_type }
    record_data: dict of the CRM record's fields
    output_type: 'pdf' | 'docx' | 'pptx' (optional, defaults to template's type)
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    template_id  = data.get('template_id')
    record_id    = data.get('record_id')
    record_data  = data.get('record_data', {})
    output_type  = data.get('output_type')

    if not template_id or not record_id:
        return jsonify({'error': 'template_id and record_id are required'}), 400

    template = DocTemplate.query.get_or_404(template_id)

    doc = GeneratedDocument(
        template_id=template_id,
        record_id=record_id,
        record_type=data.get('record_type', ''),
        output_type=output_type or template.file_type,
        status='processing',
    )
    db.session.add(doc)
    db.session.commit()

    try:
        output_path = generate_document(template, record_data, output_type)
        doc.output_path = output_path
        doc.status = 'done'
        doc.completed_at = datetime.utcnow()
    except Exception as e:
        doc.status = 'error'
        doc.error_msg = str(e)
        db.session.commit()
        return jsonify({'error': str(e)}), 500

    db.session.commit()
    return jsonify(doc.to_dict()), 201


@docgen_bp.route('/generate/bulk', methods=['POST'])
def generate_bulk():
    """
    Queue bulk generation for multiple records.
    Body: { template_id, records: [{id, record_type, record_data}], output_type }
    Uses Celery if available, falls back to synchronous processing.
    """
    data = request.get_json()
    template_id = data.get('template_id')
    records     = data.get('records', [])
    output_type = data.get('output_type')

    if not template_id or not records:
        return jsonify({'error': 'template_id and records are required'}), 400

    template = DocTemplate.query.get_or_404(template_id)

    created_docs = []
    for rec in records:
        doc = GeneratedDocument(
            template_id=template_id,
            record_id=rec.get('id'),
            record_type=rec.get('record_type', ''),
            output_type=output_type or template.file_type,
            status='pending',
        )
        db.session.add(doc)
        db.session.flush()  # get doc.id before commit

        try:
            # Try to dispatch to Celery; fall back to sync
            from .tasks import process_document_task
            process_document_task.delay(doc.id, rec.get('record_data', {}), output_type)
        except ImportError:
            # No Celery — process synchronously
            try:
                output_path = generate_document(template, rec.get('record_data', {}), output_type)
                doc.output_path = output_path
                doc.status = 'done'
                doc.completed_at = datetime.utcnow()
            except Exception as e:
                doc.status = 'error'
                doc.error_msg = str(e)

        created_docs.append(doc.to_dict())

    db.session.commit()
    return jsonify({'queued': len(created_docs), 'documents': created_docs}), 202


# ─────────────────────────────────────────────
#  DOWNLOAD + STATUS
# ─────────────────────────────────────────────

@docgen_bp.route('/download/<int:doc_id>', methods=['GET'])
def download(doc_id):
    """Download a generated document."""
    doc = GeneratedDocument.query.get_or_404(doc_id)
    if doc.status != 'done' or not doc.output_path:
        abort(404, description='Document not ready or not found')
    return send_file(doc.output_path, as_attachment=True)


@docgen_bp.route('/documents', methods=['GET'])
def list_documents():
    """List generated documents, filterable by record_id or record_type."""
    record_id   = request.args.get('record_id', type=int)
    record_type = request.args.get('record_type')
    status      = request.args.get('status')
    limit       = request.args.get('limit', 50, type=int)

    query = GeneratedDocument.query
    if record_id:
        query = query.filter_by(record_id=record_id)
    if record_type:
        query = query.filter_by(record_type=record_type)
    if status:
        query = query.filter_by(status=status)

    docs = query.order_by(GeneratedDocument.created_at.desc()).limit(limit).all()
    return jsonify([d.to_dict() for d in docs])


@docgen_bp.route('/documents/<int:doc_id>/status', methods=['GET'])
def doc_status(doc_id):
    """Poll the status of a single document (for bulk progress tracking)."""
    doc = GeneratedDocument.query.get_or_404(doc_id)
    return jsonify(doc.to_dict())
