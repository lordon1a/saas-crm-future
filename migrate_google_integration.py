"""
Migration script for Google Workspace integration tables.
Creates: google_integrations
"""
from app import app
from models import db
from models_crm import GoogleIntegration


def migrate():
    with app.app_context():
        print('Creating Google Workspace integration tables...')
        db.create_all()
        print('✓ Tables created successfully!')
        print('  - google_integrations')


if __name__ == '__main__':
    migrate()