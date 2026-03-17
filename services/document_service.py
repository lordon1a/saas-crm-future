"""Document storage and versioning service for Phase 10."""
import io
import os
import uuid
from dataclasses import dataclass
from datetime import datetime

from jinja2 import Template
from werkzeug.utils import secure_filename

from config import Config
from models import db
from models_crm import Document, DocumentTemplate, DocumentVersion


@dataclass
class StoredFileRef:
    file_path: str
    file_size: int
    mime_type: str


class LocalStorageAdapter:
    """Store document files on local filesystem."""

    def __init__(self, base_dir):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def save(self, relative_path, file_bytes):
        full_path = os.path.join(self.base_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(file_bytes)
        return relative_path

    def read(self, relative_path):
        full_path = os.path.join(self.base_dir, relative_path)
        with open(full_path, 'rb') as f:
            return f.read()


class S3StorageAdapter:
    """Store document files on S3-compatible storage using boto3."""

    def __init__(self):
        try:
            import boto3
        except Exception as exc:
            raise RuntimeError('boto3 is required for S3 storage backend') from exc

        session = boto3.session.Session(
            aws_access_key_id=Config.DOCUMENT_S3_ACCESS_KEY,
            aws_secret_access_key=Config.DOCUMENT_S3_SECRET_KEY,
            region_name=Config.DOCUMENT_S3_REGION,
        )
        self.client = session.client('s3', endpoint_url=Config.DOCUMENT_S3_ENDPOINT_URL or None)
        self.bucket = Config.DOCUMENT_S3_BUCKET
        if not self.bucket:
            raise RuntimeError('DOCUMENT_S3_BUCKET is required for S3 storage backend')

    def save(self, relative_path, file_bytes):
        self.client.put_object(Bucket=self.bucket, Key=relative_path, Body=file_bytes)
        return relative_path

    def read(self, relative_path):
        obj = self.client.get_object(Bucket=self.bucket, Key=relative_path)
        return obj['Body'].read()


class DocumentService:
    """Main business service for document management and versioning."""

    @staticmethod
    def max_file_size_bytes():
        return int(Config.DOCUMENT_MAX_SIZE_MB) * 1024 * 1024

    @staticmethod
    def _get_storage_adapter():
        backend = (Config.DOCUMENT_STORAGE_BACKEND or 'local').lower()
        if backend == 's3':
            return S3StorageAdapter()
        return LocalStorageAdapter(Config.DOCUMENT_LOCAL_BASE_DIR)

    @staticmethod
    def _workspace_relative_path(workspace_id, original_filename):
        safe_name = secure_filename(original_filename or 'document.bin')
        ext = os.path.splitext(safe_name)[1] or ''
        unique = uuid.uuid4().hex
        return os.path.join(
            'workspace_' + str(workspace_id),
            datetime.utcnow().strftime('%Y'),
            datetime.utcnow().strftime('%m'),
            f'{unique}{ext}',
        )

    @staticmethod
    def _read_file_bytes(file_storage):
        content = file_storage.read()
        file_storage.stream.seek(0)
        size = len(content)
        if size > DocumentService.max_file_size_bytes():
            raise ValueError(f'File size exceeds {Config.DOCUMENT_MAX_SIZE_MB}MB limit')
        return content, size

    @staticmethod
    def create_document(workspace_id, uploaded_by, file_storage, name=None, category='general',
                        company_id=None, deal_id=None, is_customer_visible=False):
        if not file_storage:
            raise ValueError('File is required')

        file_bytes, file_size = DocumentService._read_file_bytes(file_storage)
        mime_type = (file_storage.mimetype or 'application/octet-stream')[:100]
        doc_name = (name or file_storage.filename or 'Unnamed Document').strip()

        try:
            document = Document(
                workspace_id=workspace_id,
                name=doc_name,
                category=(category or 'general').strip(),
                company_id=company_id,
                deal_id=deal_id,
                uploaded_by=uploaded_by,
                is_customer_visible=bool(is_customer_visible),
            )
            db.session.add(document)
            db.session.flush()

            relative_path = DocumentService._workspace_relative_path(workspace_id, file_storage.filename)
            storage = DocumentService._get_storage_adapter()
            stored_path = storage.save(relative_path, file_bytes)

            version = DocumentVersion(
                document_id=document.id,
                version_number=1,
                file_path=stored_path,
                file_size=file_size,
                mime_type=mime_type,
                uploaded_by=uploaded_by,
            )
            db.session.add(version)
            db.session.flush()

            document.current_version_id = version.id
            db.session.commit()
            return document
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def add_version(workspace_id, document_id, uploaded_by, file_storage):
        document = Document.query.filter_by(id=document_id, workspace_id=workspace_id).first()
        if not document:
            raise ValueError('Document not found')
        if not file_storage:
            raise ValueError('File is required')

        file_bytes, file_size = DocumentService._read_file_bytes(file_storage)
        mime_type = (file_storage.mimetype or 'application/octet-stream')[:100]

        latest = DocumentVersion.query.filter_by(document_id=document.id).order_by(DocumentVersion.version_number.desc()).first()
        next_version = 1 if not latest else latest.version_number + 1

        try:
            relative_path = DocumentService._workspace_relative_path(workspace_id, file_storage.filename)
            storage = DocumentService._get_storage_adapter()
            stored_path = storage.save(relative_path, file_bytes)

            version = DocumentVersion(
                document_id=document.id,
                version_number=next_version,
                file_path=stored_path,
                file_size=file_size,
                mime_type=mime_type,
                uploaded_by=uploaded_by,
            )
            db.session.add(version)
            db.session.flush()

            document.current_version_id = version.id
            db.session.commit()
            return version
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def list_documents(workspace_id, category=None, page=1, per_page=20):
        query = Document.query.filter_by(workspace_id=workspace_id)
        if category:
            query = query.filter_by(category=category)

        pagination = query.order_by(Document.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        items = []
        for row in pagination.items:
            latest = DocumentVersion.query.filter_by(document_id=row.id).order_by(DocumentVersion.version_number.desc()).first()
            items.append({
                'id': row.id,
                'name': row.name,
                'category': row.category,
                'company_id': row.company_id,
                'deal_id': row.deal_id,
                'is_customer_visible': row.is_customer_visible,
                'created_at': row.created_at.isoformat() if row.created_at else None,
                'current_version': latest.version_number if latest else None,
                'file_size': latest.file_size if latest else None,
                'mime_type': latest.mime_type if latest else None,
            })

        return {
            'items': items,
            'total': pagination.total,
            'page': pagination.page,
            'per_page': pagination.per_page,
            'pages': pagination.pages,
        }

    @staticmethod
    def get_document_versions(workspace_id, document_id):
        document = Document.query.filter_by(id=document_id, workspace_id=workspace_id).first()
        if not document:
            raise ValueError('Document not found')

        rows = DocumentVersion.query.filter_by(document_id=document.id).order_by(DocumentVersion.version_number.desc()).all()
        return [
            {
                'id': row.id,
                'version_number': row.version_number,
                'file_size': row.file_size,
                'mime_type': row.mime_type,
                'created_at': row.created_at.isoformat() if row.created_at else None,
                'uploaded_by': row.uploaded_by,
            }
            for row in rows
        ]

    @staticmethod
    def get_file_payload(workspace_id, document_id, version_id=None):
        document = Document.query.filter_by(id=document_id, workspace_id=workspace_id).first()
        if not document:
            raise ValueError('Document not found')

        if version_id:
            version = DocumentVersion.query.filter_by(id=version_id, document_id=document.id).first()
        else:
            version = DocumentVersion.query.filter_by(document_id=document.id).order_by(DocumentVersion.version_number.desc()).first()

        if not version:
            raise ValueError('Document version not found')

        storage = DocumentService._get_storage_adapter()
        payload = storage.read(version.file_path)

        return {
            'bytes': payload,
            'mime_type': version.mime_type or 'application/octet-stream',
            'download_name': secure_filename(document.name) or f'document_{document.id}',
            'version_number': version.version_number,
        }

    @staticmethod
    def render_template_content(template_body, variables):
        """Render Jinja2 template body with restricted input mapping."""
        template = Template(template_body or '')
        return template.render(**(variables or {}))

    @staticmethod
    def create_document_template(workspace_id, name, category, template_body, variables):
        row = DocumentTemplate(
            workspace_id=workspace_id,
            name=(name or '').strip(),
            category=(category or 'general').strip(),
            file_path='',
            variables=','.join(variables or []),
        )
        # Using file_path field for backward compatibility: store template body inline with a prefix.
        row.file_path = 'inline:' + (template_body or '')
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def list_document_templates(workspace_id):
        rows = DocumentTemplate.query.filter_by(workspace_id=workspace_id).order_by(DocumentTemplate.created_at.desc()).all()
        out = []
        for row in rows:
            body = row.file_path[7:] if (row.file_path or '').startswith('inline:') else ''
            out.append({
                'id': row.id,
                'name': row.name,
                'category': row.category,
                'variables': [v.strip() for v in (row.variables or '').split(',') if v.strip()],
                'template_body': body,
            })
        return out

    @staticmethod
    def render_saved_template(workspace_id, template_id, variables):
        row = DocumentTemplate.query.filter_by(workspace_id=workspace_id, id=template_id).first()
        if not row:
            raise ValueError('Template not found')
        body = row.file_path[7:] if (row.file_path or '').startswith('inline:') else ''
        return DocumentService.render_template_content(body, variables)
