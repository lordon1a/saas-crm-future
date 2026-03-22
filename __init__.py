"""
docgen/__init__.py
"""
from .routes import docgen_bp
from .models import db

__all__ = ['docgen_bp', 'db']


# ─────────────────────────────────────────────
#  HOW TO INTEGRATE INTO YOUR FLASK APP
# ─────────────────────────────────────────────
#
# In your app.py / create_app():
#
#   from docgen import docgen_bp, db
#
#   def create_app():
#       app = Flask(__name__)
#       app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@localhost/yourdb'
#       app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#
#       db.init_app(app)
#
#       app.register_blueprint(docgen_bp, url_prefix='/docgen')
#
#       with app.app_context():
#           db.create_all()   # creates doc_templates + generated_documents tables
#
#       return app
#
#
# ─────────────────────────────────────────────
#  RECORD PAGE — CALLING FROM FRONTEND (JS)
# ─────────────────────────────────────────────
#
#   // 1. Get available templates for this object type
#   const res = await fetch('/docgen/templates?object_type=Lead');
#   const templates = await res.json();
#
#   // 2. Generate a document
#   await fetch('/docgen/generate', {
#     method: 'POST',
#     headers: { 'Content-Type': 'application/json' },
#     body: JSON.stringify({
#       template_id: 3,
#       record_id: 42,
#       record_type: 'Lead',
#       output_type: 'pdf',          // or 'docx', 'pptx'
#       record_data: {               // pass the full record fields
#         name: 'Ahmet Yılmaz',
#         email: 'ahmet@firma.com',
#         deal_value: '50000 TL',
#       }
#     })
#   });
#
#
# ─────────────────────────────────────────────
#  REQUIRED PACKAGES
# ─────────────────────────────────────────────
#
#   pip install docxtpl python-pptx weasyprint jinja2 celery redis
#   apt-get install libreoffice   # only needed for docx → pdf conversion
#
#
# ─────────────────────────────────────────────
#  DATABASE MIGRATION (if using Flask-Migrate)
# ─────────────────────────────────────────────
#
#   flask db migrate -m "add docgen tables"
#   flask db upgrade
