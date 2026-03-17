import shutil
import tempfile
import unittest
from io import BytesIO

from flask import Flask
from werkzeug.datastructures import FileStorage

from config import Config
from models import Workspace, User, db
import models_crm  # noqa: F401
from services.document_service import DocumentService


class TestPhase10Documents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(cls.app)

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.temp_dir = tempfile.mkdtemp(prefix='doc-test-')
        Config.DOCUMENT_STORAGE_BACKEND = 'local'
        Config.DOCUMENT_LOCAL_BASE_DIR = self.temp_dir
        Config.DOCUMENT_MAX_SIZE_MB = 1

        ws = Workspace(company_name='Doc Test Workspace')
        db.session.add(ws)
        db.session.flush()

        user = User(
            workspace_id=ws.id,
            name='Doc User',
            email='doc.user@example.com',
            password_hash='hash',
            role='admin',
        )
        db.session.add(user)
        db.session.commit()

        self.workspace_id = ws.id
        self.user_id = user.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _file(self, content, filename='sample.txt', mimetype='text/plain'):
        return FileStorage(stream=BytesIO(content), filename=filename, content_type=mimetype)

    def test_file_size_limit_enforced(self):
        too_large = b'a' * (DocumentService.max_file_size_bytes() + 1)
        with self.assertRaises(ValueError):
            DocumentService.create_document(
                workspace_id=self.workspace_id,
                uploaded_by=self.user_id,
                file_storage=self._file(too_large, filename='big.bin', mimetype='application/octet-stream'),
                name='Too Big',
                category='general',
            )

    def test_document_version_history(self):
        doc = DocumentService.create_document(
            workspace_id=self.workspace_id,
            uploaded_by=self.user_id,
            file_storage=self._file(b'v1 content', filename='contract.txt'),
            name='Contract',
            category='contract',
        )

        version2 = DocumentService.add_version(
            workspace_id=self.workspace_id,
            document_id=doc.id,
            uploaded_by=self.user_id,
            file_storage=self._file(b'v2 content', filename='contract-v2.txt'),
        )

        self.assertEqual(version2.version_number, 2)

        versions = DocumentService.get_document_versions(self.workspace_id, doc.id)
        self.assertEqual([row['version_number'] for row in versions], [2, 1])

    def test_template_variable_substitution(self):
        rendered = DocumentService.render_template_content(
            'Merhaba {{ contact_name }}, {{ company_name }} teklif tutari {{ deal_value }}.',
            {
                'contact_name': 'Ayse',
                'company_name': 'Acme',
                'deal_value': '1000',
            },
        )
        self.assertIn('Ayse', rendered)
        self.assertIn('Acme', rendered)
        self.assertIn('1000', rendered)

    def test_category_filtering(self):
        DocumentService.create_document(
            workspace_id=self.workspace_id,
            uploaded_by=self.user_id,
            file_storage=self._file(b'proposal body', filename='proposal.txt'),
            name='Proposal',
            category='proposal',
        )
        DocumentService.create_document(
            workspace_id=self.workspace_id,
            uploaded_by=self.user_id,
            file_storage=self._file(b'invoice body', filename='invoice.txt'),
            name='Invoice',
            category='invoice',
        )

        payload = DocumentService.list_documents(
            workspace_id=self.workspace_id,
            category='invoice',
            page=1,
            per_page=20,
        )

        self.assertEqual(payload['total'], 1)
        self.assertEqual(payload['items'][0]['category'], 'invoice')


if __name__ == '__main__':
    unittest.main()
