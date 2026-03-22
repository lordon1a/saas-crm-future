"""
Celery tasks for async document generation.

pip install celery redis
Run worker: celery -A your_app.celery worker --loglevel=info
"""

from datetime import datetime
from celery import Celery

# Initialize Celery — replace broker URL with your Redis instance
celery = Celery('docgen', broker='redis://localhost:6379/0')


@celery.task(bind=True, max_retries=3, default_retry_delay=5)
def process_document_task(self, doc_id: int, record_data: dict, output_type: str = None):
    """
    Async Celery task to generate a single document.
    Retries up to 3 times on failure.
    """
    # Import here to avoid circular imports
    from .models import db, DocTemplate, GeneratedDocument
    from .engine import generate_document

    doc = GeneratedDocument.query.get(doc_id)
    if not doc:
        return {'error': f'Document {doc_id} not found'}

    doc.status = 'processing'
    db.session.commit()

    try:
        template = DocTemplate.query.get(doc.template_id)
        output_path = generate_document(template, record_data, output_type)

        doc.output_path = output_path
        doc.status = 'done'
        doc.completed_at = datetime.utcnow()
        db.session.commit()
        return {'doc_id': doc_id, 'status': 'done', 'output': output_path}

    except Exception as exc:
        doc.status = 'error'
        doc.error_msg = str(exc)
        db.session.commit()
        raise self.retry(exc=exc)
