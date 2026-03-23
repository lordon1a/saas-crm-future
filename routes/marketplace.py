"""
Marketplace routes for app installation/management
"""
from flask import Blueprint, render_template, request, jsonify, session, flash
from models import db
from models_crm import WorkspaceApp
from functools import wraps
import logging

logger = logging.getLogger(__name__)

marketplace_bp = Blueprint('marketplace', __name__)


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        if 'workspace_id' not in session:
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated_function

# App catalog - static list of available apps
APP_CATALOG = [
    {
        "slug": "docgen",
        "name": "Belge Üretici",
        "description": "Anlaşma ve tekliflerden otomatik PDF, DOCX, PPTX üret",
        "icon": "fa-file-alt",
        "color": "purple",
        "category": "Verimlilik",
        "is_available": True,
    },
    {
        "slug": "email_campaigns",
        "name": "E-posta Kampanyaları",
        "description": "Toplu e-posta gönder, açılma oranlarını takip et",
        "icon": "fa-envelope",
        "color": "blue",
        "category": "Pazarlama",
        "is_available": False,  # Yakında
    },
    {
        "slug": "sms_notifier",
        "name": "SMS Bildirimleri",
        "description": "Müşterilere otomatik SMS gönder",
        "icon": "fa-comment-sms",
        "color": "green",
        "category": "Pazarlama",
        "is_available": False,
    },
    {
        "slug": "ai_assistant",
        "name": "AI Asistan",
        "description": "CRM verilerinizi analiz eden yapay zeka asistanı",
        "icon": "fa-robot",
        "color": "amber",
        "category": "Yapay Zeka",
        "is_available": False,
    },
]


@marketplace_bp.route('/marketplace/test')
@login_required
def test_page():
    """Debug test page for installed apps"""
    return render_template('test_installed_apps.html')


@marketplace_bp.route('/marketplace')
@login_required
def marketplace_page():
    """Render marketplace page with catalog and installed apps"""
    try:
        workspace_id = session.get('workspace_id')
        
        # Get installed apps for current workspace
        installed_apps = WorkspaceApp.query.filter_by(
            workspace_id=workspace_id,
            is_active=True
        ).all()
        
        installed_slugs = [app.app_slug for app in installed_apps]
        
        return render_template(
            'marketplace.html',
            catalog=APP_CATALOG,
            installed_apps=installed_slugs
        )
    except Exception as e:
        logger.error(f"Error loading marketplace: {e}")
        return render_template('marketplace.html', catalog=APP_CATALOG, installed_apps=[])


@marketplace_bp.route('/api/marketplace/install', methods=['POST'])
@login_required
def install_app():
    """Install an app for the current workspace"""
    try:
        data = request.get_json()
        app_slug = data.get('app_slug')
        workspace_id = session.get('workspace_id')
        
        if not app_slug:
            return jsonify({'error': 'app_slug gerekli'}), 400
        
        # Check if app exists in catalog
        app_info = next((app for app in APP_CATALOG if app['slug'] == app_slug), None)
        if not app_info:
            return jsonify({'error': 'Uygulama bulunamadı'}), 404
        
        if not app_info['is_available']:
            return jsonify({'error': 'Bu uygulama henüz kullanıma açık değil'}), 400
        
        # Check if already installed
        existing = WorkspaceApp.query.filter_by(
            workspace_id=workspace_id,
            app_slug=app_slug
        ).first()
        
        if existing:
            if existing.is_active:
                return jsonify({'message': 'Uygulama zaten yüklü'}), 200
            else:
                # Reactivate
                existing.is_active = True
                db.session.commit()
                return jsonify({'message': 'Uygulama yeniden aktif edildi'}), 200
        
        # Create new installation
        new_app = WorkspaceApp(
            workspace_id=workspace_id,
            app_slug=app_slug,
            is_active=True
        )
        db.session.add(new_app)
        db.session.commit()
        
        # Get app name for flash message
        app_names = {
            'docgen': 'Belge Üretici',
            'email_campaigns': 'E-posta Kampanyaları',
            'sms_notifier': 'SMS Bildirimleri',
            'ai_assistant': 'AI Asistan'
        }
        app_name = app_names.get(app_slug, app_slug)
        
        logger.info(f"App '{app_slug}' installed for workspace {workspace_id}")
        flash(f'{app_name} başarıyla yüklendi', 'marketplace_success')
        return jsonify({'message': 'Uygulama başarıyla yüklendi'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error installing app: {e}")
        return jsonify({'error': 'Yükleme sırasında hata oluştu'}), 500


@marketplace_bp.route('/api/marketplace/uninstall', methods=['POST'])
@login_required
def uninstall_app():
    """Uninstall an app from the current workspace"""
    try:
        data = request.get_json()
        app_slug = data.get('app_slug')
        workspace_id = session.get('workspace_id')
        
        if not app_slug:
            return jsonify({'error': 'app_slug gerekli'}), 400
        
        # Find and deactivate the app
        app = WorkspaceApp.query.filter_by(
            workspace_id=workspace_id,
            app_slug=app_slug
        ).first()
        
        if not app:
            return jsonify({'error': 'Uygulama yüklü değil'}), 404
        
        # Soft delete - just deactivate
        app.is_active = False
        db.session.commit()
        
        logger.info(f"App '{app_slug}' uninstalled from workspace {workspace_id}")
        return jsonify({'message': 'Uygulama kaldırıldı'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uninstalling app: {e}")
        return jsonify({'error': 'Kaldırma sırasında hata oluştu'}), 500


@marketplace_bp.route('/api/marketplace/installed')
@login_required
def get_installed_apps():
    """Get list of installed app slugs for current workspace"""
    try:
        workspace_id = session.get('workspace_id')
        
        installed = WorkspaceApp.query.filter_by(
            workspace_id=workspace_id,
            is_active=True
        ).with_entities(WorkspaceApp.app_slug).all()
        
        slugs = [app.app_slug for app in installed]
        return jsonify({'installed_apps': slugs}), 200
        
    except Exception as e:
        logger.error(f"Error fetching installed apps: {e}")
        return jsonify({'error': 'Yüklü uygulamalar alınamadı'}), 500


@marketplace_bp.route('/api/marketplace/debug')
@login_required
def debug_installed_apps():
    """Debug endpoint to check installed apps and context"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        # Query database
        installed = WorkspaceApp.query.filter_by(
            workspace_id=workspace_id,
            is_active=True
        ).all()
        
        # Get all apps (including inactive)
        all_apps = WorkspaceApp.query.filter_by(
            workspace_id=workspace_id
        ).all()
        
        return jsonify({
            'session': {
                'user_id': user_id,
                'workspace_id': workspace_id
            },
            'installed_apps': [{'slug': app.app_slug, 'active': app.is_active} for app in installed],
            'all_apps': [{'slug': app.app_slug, 'active': app.is_active} for app in all_apps],
            'installed_slugs': [app.app_slug for app in installed]
        }), 200
        
    except Exception as e:
        logger.error(f"Debug error: {e}")
        return jsonify({'error': str(e)}), 500
