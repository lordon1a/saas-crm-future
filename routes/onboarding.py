from flask import Blueprint, jsonify, session, render_template
from functools import wraps
from models_crm import OnboardingProgress, Contact, Company, Deal, Pipeline, DealStage
from models import db, User
from datetime import datetime

bp = Blueprint('onboarding', __name__)

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

STEPS = {
    'profile_setup': {
        'key': 'profile_setup',
        'title': 'Profilini düzenle',
        'description': 'Adını ve profil resmini güncelle',
        'icon': 'fa-user-edit',
        'link': '/settings?tab=profile',
        'estimated_time': '1-2 dk',
        'action_label': 'Profiline Git',
        'tracked': True,
    },
    'channel_connected': {
        'key': 'channel_connected',
        'title': 'Mesajlaşma kanalı bağla',
        'description': 'WhatsApp veya Telegram hesabını bağla',
        'icon': 'fa-plug',
        'link': '/channels',
        'estimated_time': '2-3 dk',
        'action_label': 'Kanalları Yönet',
        'tracked': True,
    },
    'first_contact_added': {
        'key': 'first_contact_added',
        'title': 'İlk kişiyi ekle',
        'description': 'Bir müşteri veya potansiyel lead ekle',
        'icon': 'fa-user-plus',
        'link': '/contacts',
        'estimated_time': '1-2 dk',
        'action_label': 'Kişi Ekle',
        'tracked': True,
    },
    'import_contacts': {
        'key': 'import_contacts',
        'title': 'Kişileri içe aktar',
        'description': 'CSV veya Excel dosyasından toplu kişi yükle',
        'icon': 'fa-file-import',
        'link': '/import',
        'estimated_time': '3-5 dk',
        'action_label': 'İçe Aktar',
        'tracked': False,
    },
    'first_deal_created': {
        'key': 'first_deal_created',
        'title': 'İlk deal oluştur',
        'description': "Pipeline'ına bir satış fırsatı ekle",
        'icon': 'fa-handshake',
        'link': '/pipeline',
        'estimated_time': '2-4 dk',
        'action_label': 'Fırsat Oluştur',
        'tracked': True,
    },
    'team_member_invited': {
        'key': 'team_member_invited',
        'title': 'Ekip üyesi davet et',
        'description': "Ekibini CRM'e davet et",
        'icon': 'fa-user-friends',
        'link': '/settings?tab=team',
        'estimated_time': '1-2 dk',
        'action_label': 'Ekibi Davet Et',
        'tracked': True,
    },
    'send_broadcast': {
        'key': 'send_broadcast',
        'title': 'Toplu mesaj gönder',
        'description': 'Müşteri segmentine otomatik mesaj gönder',
        'icon': 'fa-bullhorn',
        'link': '/broadcast',
        'estimated_time': '3-5 dk',
        'action_label': 'Toplu Mesaj',
        'tracked': False,
    },
    'setup_automation': {
        'key': 'setup_automation',
        'title': 'Otomasyon kur',
        'description': 'Tekrarlayan işleri otomatikleştir',
        'icon': 'fa-robot',
        'link': '/automation',
        'estimated_time': '5-10 dk',
        'action_label': 'Otomasyon Kur',
        'tracked': False,
    },
    'view_analytics': {
        'key': 'view_analytics',
        'title': 'Raporları incele',
        'description': 'Satış performansını ve iletişim verilerini analiz et',
        'icon': 'fa-chart-line',
        'link': '/analytics',
        'estimated_time': '2-3 dk',
        'action_label': 'Analitik Görüntüle',
        'tracked': False,
    },
    'setup_pipeline': {
        'key': 'setup_pipeline',
        'title': "Pipeline'ını özelleştir",
        'description': 'Satış aşamalarını iş sürecine göre düzenle',
        'icon': 'fa-filter',
        'link': '/pipeline',
        'estimated_time': '3-5 dk',
        'action_label': "Pipeline'a Git",
        'tracked': False,
    },
}

STEP_GROUPS = [
    {
        'key': 'basics',
        'title': 'Temel Kurulumu Tamamla',
        'icon': 'fa-rocket',
        'steps': ['profile_setup', 'channel_connected', 'first_contact_added'],
    },
    {
        'key': 'sales',
        'title': 'Satış Sürecini Kur',
        'icon': 'fa-filter',
        'steps': ['first_deal_created', 'setup_pipeline', 'team_member_invited'],
    },
    {
        'key': 'communication',
        'title': 'İletişimi Güçlendir',
        'icon': 'fa-comments',
        'steps': ['send_broadcast', 'setup_automation'],
    },
    {
        'key': 'data',
        'title': 'Verileri Yönet',
        'icon': 'fa-database',
        'steps': ['import_contacts', 'view_analytics'],
    },
]

@bp.route('/setup-guide')
@login_required
def setup_guide():
    """Render the full-page setup guide (Pipedrive style)"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    workspace_id = user.workspace_id if user else None
    
    onboarding_complete = False
    if workspace_id:
        from services.onboarding_service import OnboardingService
        progress = OnboardingService.get_progress(workspace_id)
        onboarding_complete = progress.is_complete
    
    return render_template('onboarding_guide.html', onboarding_complete=onboarding_complete)

@bp.route('/api/onboarding/progress', methods=['GET'])
@login_required
def get_progress():
    try:
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        workspace_id = user.workspace_id
        from services.onboarding_service import OnboardingService
        progress = OnboardingService.get_progress(workspace_id)
    except Exception as e:
        print(f"❌ Onboarding query error: {e}")
        return jsonify({'error': str(e)}), 500

    # Build groups with step completion data
    # Untracked steps use a simple key-based fallback (always False from DB)
    groups_data = []
    all_steps_flat = []
    for group in STEP_GROUPS:
        group_steps = []
        for step_key in group['steps']:
            step = STEPS.get(step_key)
            if not step:
                continue
            completed = getattr(progress, step_key, False) if step['tracked'] else False
            step_data = {**step, 'completed': completed}
            group_steps.append(step_data)
            all_steps_flat.append(step_data)
        done = sum(1 for s in group_steps if s['completed'])
        groups_data.append({
            'key': group['key'],
            'title': group['title'],
            'icon': group['icon'],
            'steps': group_steps,
            'done': done,
            'total': len(group_steps),
        })

    return jsonify({
        'groups': groups_data,
        'steps': all_steps_flat,
        'percent': progress.completion_percent,
        'is_complete': progress.is_complete,
        'show': not progress.is_complete
    })


@bp.route('/api/onboarding/complete/<step_key>', methods=['POST'])
@login_required
def complete_step(step_key):
    """Bir onboarding adımını tamamla."""
    step = STEPS.get(step_key)
    if not step:
        return jsonify({'error': 'Geçersiz adım'}), 400

    # Untracked steps: nothing to write to DB, just return success
    if not step.get('tracked', True):
        return jsonify({'success': True, 'percent': None, 'untracked': True})

    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    workspace_id = user.workspace_id
    from services.onboarding_service import OnboardingService
    success = OnboardingService.complete_step(workspace_id, step_key)
    
    if success:
        progress = OnboardingService.get_progress(workspace_id)
        return jsonify({'success': True, 'percent': progress.completion_percent})
    else:
        return jsonify({'error': 'Failed to complete step'}), 500


@bp.route('/api/onboarding/dismiss', methods=['POST'])
@login_required
def dismiss():
    """Kullanıcı checklist'i kapatmak isterse tüm adımları tamamlanmış say."""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    workspace_id = user.workspace_id
    from services.onboarding_service import OnboardingService
    
    # Mark all tracked steps as complete
    for step in STEPS.values():
        if step.get('tracked', True):
            OnboardingService.complete_step(workspace_id, step['key'])
    
    # Mark user's first login as complete
    user.is_first_login = False
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/api/onboarding/load-demo', methods=['POST'])
@login_required
def load_demo_data():
    """Workspace'e örnek veri yükle."""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    workspace_id = user.workspace_id
    
    # Zaten demo veri var mı?
    existing = Contact.query.filter_by(workspace_id=workspace_id).count()
    if existing > 5:
        return jsonify({'error': 'Zaten veri mevcut'}), 400
    
    demo_companies = [
        {'name': 'Teknoloji A.Ş', 'industry': 'Yazılım'},
        {'name': 'Medya Ltd', 'industry': 'Medya'},
        {'name': 'Finans Corp', 'industry': 'Finans'},
    ]
    
    demo_contacts = [
        {'first_name': 'Ahmet', 'last_name': 'Yılmaz', 'email': 'ahmet@tekno.com', 'phone': '+905551234567'},
        {'first_name': 'Ayşe', 'last_name': 'Kaya', 'email': 'ayse@medya.com', 'phone': '+905559876543'},
        {'first_name': 'Mehmet', 'last_name': 'Demir', 'email': 'mehmet@finans.com', 'phone': '+905551112233'},
    ]
    
    demo_deals = [
        {'name': 'Yazılım Lisansı', 'value': 15000, 'status': 'open', 'next_step': 'Demo toplantısı planla'},
        {'name': 'Reklam Kampanyası', 'value': 8500, 'status': 'open', 'next_step': 'Teklif gönder'},
        {'name': 'Danışmanlık', 'value': 25000, 'status': 'won', 'next_step': 'Sözleşmeyi tamamla'},
    ]
    
    try:
        pipeline = Pipeline.query.filter_by(workspace_id=workspace_id, is_default=True).first()
        if not pipeline:
            pipeline = Pipeline(
                workspace_id=workspace_id,
                name='Sales Pipeline',
                is_default=True
            )
            db.session.add(pipeline)
            db.session.flush()

            default_stages = [
                {'name': 'Lead', 'order': 1, 'probability': 10, 'rotting_days': 7},
                {'name': 'Qualified', 'order': 2, 'probability': 25, 'rotting_days': 7},
                {'name': 'Proposal', 'order': 3, 'probability': 50, 'rotting_days': 14},
                {'name': 'Negotiation', 'order': 4, 'probability': 75, 'rotting_days': 14},
                {'name': 'Closed Won', 'order': 5, 'probability': 100, 'rotting_days': None},
                {'name': 'Closed Lost', 'order': 6, 'probability': 0, 'rotting_days': None},
            ]
            for stage_data in default_stages:
                db.session.add(DealStage(
                    pipeline_id=pipeline.id,
                    name=stage_data['name'],
                    order=stage_data['order'],
                    probability=stage_data['probability'],
                    rotting_days=stage_data['rotting_days'],
                    is_active=True
                ))
            db.session.flush()

        open_stage = DealStage.query.filter_by(
            pipeline_id=pipeline.id,
            is_active=True
        ).order_by(DealStage.order.asc()).first()
        won_stage = DealStage.query.filter(
            DealStage.pipeline_id == pipeline.id,
            DealStage.is_active.is_(True),
            DealStage.name.ilike('%won%')
        ).first()

        if not open_stage:
            return jsonify({'error': 'Pipeline stage not found'}), 500

        companies = []
        for c in demo_companies:
            company = Company(workspace_id=workspace_id, **c)
            db.session.add(company)
            companies.append(company)
        db.session.flush()
        
        contacts = []
        for i, c in enumerate(demo_contacts):
            contact = Contact(workspace_id=workspace_id, company_id=companies[i].id, **c)
            db.session.add(contact)
            contacts.append(contact)
        db.session.flush()
        
        for i, d in enumerate(demo_deals):
            is_won = d['status'] == 'won'
            stage = won_stage if (is_won and won_stage) else open_stage
            deal = Deal(
                workspace_id=workspace_id,
                name=d['name'],
                value=d['value'],
                status=d['status'],
                next_step=d['next_step'],
                company_id=companies[i].id,
                contact_id=contacts[i].id,
                pipeline_id=pipeline.id,
                stage_id=stage.id,
                owner_id=user.id,
                closed_at=datetime.utcnow() if is_won else None
            )
            db.session.add(deal)
        
        db.session.commit()
        from services.onboarding_service import OnboardingService
        OnboardingService.complete_step(workspace_id, 'first_contact_added')
        OnboardingService.complete_step(workspace_id, 'first_deal_created')
        return jsonify({'success': True, 'message': '3 şirket, 3 kişi ve 3 deal eklendi'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
