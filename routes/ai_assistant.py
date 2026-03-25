import os
import requests
import google.generativeai as genai
import anthropic
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify, g, session
from utils.app_guard import require_app

bp = Blueprint('ai_assistant', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        if 'workspace_id' not in session:
            return jsonify({'error': 'Workspace context missing'}), 401
        return f(*args, **kwargs)
    return decorated_function

from models_crm import Deal, Contact, Company, Activity, Task
from models import Conversation, Message, db

# Initialize fallback clients from env vars
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY')
GROQ_KEY = os.environ.get('GROQ_API_KEY')

gemini_client = None
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    gemini_client = genai

anthropic_client = None
if ANTHROPIC_KEY:
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

groq_client = None
if GROQ_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_KEY)
    except ImportError:
        pass  # groq package not installed


def _get_workspace_ai(workspace_id):
    """Get AI clients and model names for a workspace.
    Priority: workspace DB settings > env vars.
    Returns dict with gemini_client, anthropic_client, groq_client, and model names.
    """
    import logging
    logger = logging.getLogger(__name__)

    result = {
        'gemini_client': gemini_client,
        'anthropic_client': anthropic_client,
        'groq_client': groq_client,
        'gemini_key': GEMINI_KEY,
        'anthropic_key': ANTHROPIC_KEY,
        'groq_key': GROQ_KEY,
        'openrouter_key': None,
        'gemini_model': 'gemini-2.5-flash',
        'anthropic_model': 'claude-3-5-sonnet-latest',
        'groq_model': 'llama-3.1-70b-versatile',
        'openrouter_model': 'openrouter/auto',
    }
    try:
        from models_crm import AISettings
        import hashlib, base64
        from cryptography.fernet import Fernet
        from config import Config

        key_material = Config.SECRET_KEY.encode('utf-8')
        digest = hashlib.sha256(key_material).digest()
        fernet = Fernet(base64.urlsafe_b64encode(digest))

        rows = AISettings.query.filter_by(workspace_id=workspace_id, is_active=True).all()
        logger.info(f"[AI] Found {len(rows)} AI settings for workspace {workspace_id}")
        for row in rows:
            if not row.api_key_encrypted:
                continue
            try:
                decrypted = fernet.decrypt(row.api_key_encrypted.encode('utf-8')).decode('utf-8')
            except Exception as dec_err:
                logger.warning(f"[AI] Failed to decrypt key for {row.provider}: {dec_err}")
                continue

            if row.provider == 'gemini' and decrypted:
                genai.configure(api_key=decrypted)
                result['gemini_client'] = genai
                result['gemini_key'] = decrypted
                if row.model_name:
                    result['gemini_model'] = row.model_name
                logger.info(f"[AI] Using workspace Gemini key, model={result['gemini_model']}")
            elif row.provider == 'anthropic' and decrypted:
                result['anthropic_client'] = anthropic.Anthropic(api_key=decrypted)
                result['anthropic_key'] = decrypted
                if row.model_name:
                    result['anthropic_model'] = row.model_name
                logger.info(f"[AI] Using workspace Anthropic key, model={result['anthropic_model']}")
            elif row.provider == 'openrouter' and decrypted:
                result['openrouter_key'] = decrypted
                if row.model_name:
                    result['openrouter_model'] = row.model_name
                logger.info(f"[AI] Using workspace OpenRouter key, model={result['openrouter_model']}")
            elif row.provider == 'groq' and decrypted:
                try:
                    from groq import Groq
                    result['groq_client'] = Groq(api_key=decrypted)
                    result['groq_key'] = decrypted
                    if row.model_name:
                        result['groq_model'] = row.model_name
                    logger.info(f"[AI] Using workspace Groq key, model={result['groq_model']}")
                except ImportError:
                    logger.warning("[AI] Groq package not installed")
    except Exception as e:
        logger.error(f"[AI] Failed to load workspace AI settings: {e}")
    return result

SYSTEM_PROMPT = """You are a CRM assistant. Respond in Turkish.

Rules:
- "hello"/"hi"/"thanks" → brief friendly reply only
- Action request → return pure JSON (no markdown, no explanation)
- Use context data when available"""

ACTION_SYSTEM = """

JSON ACTION FORMAT (when user requests action):
{"requires_confirmation": true, "action": "ACTION_NAME", "params": {PARAMS}, "message": "Turkish message"}

CRITICAL RULES:
1. Return ONLY the JSON above. NO markdown fence, NO explanation, NO extra text.
2. "requires_confirmation" MUST ALWAYS be true
3. Extract real names from context or user message - NO placeholders like "Isim Soyisim"

Actions:
- create_contact: {isim, email, telefon}
- update_contact: {isim (REQUIRED - use real name from context/message), role/email/telefon/sirket/pozisyon}
- create_deal: {isim, deger, sirket}
- update_deal_status: {deal_id, status}
- update_deal_value: {deal_id, value}

IMPORTANT DISTINCTION:
- "role" = Decision Maker, Influencer, Champion, Blocker, End User (business role in deal)
- "pozisyon" = job title like "CEO", "Manager", "Engineer" (job position)

When user says "change role to Decision Maker" → use "role" parameter, NOT "pozisyon"

Example: User says "change Yiğit Güldal's role to Decision Maker"
Correct: {"requires_confirmation": true, "action": "update_contact", "params": {"isim": "Yiğit Güldal", "role": "Decision Maker"}, "message": "Yiğit Güldal'ın rolü Decision Maker olarak güncellenecek"}
"""


@bp.route('/api/ai/chat', methods=['POST'])
@login_required
@require_app('ai_assistant')
def chat():
    import json as json_lib
    data = request.get_json()
    messages = data.get('messages', [])
    context = data.get('context', {})

    if not messages:
        return jsonify({'error': 'Mesaj gerekli'}), 400

    # SON 10 MESAJI AL (token tasarrufu için)
    # İlk mesaj varsa onu koru (context için önemli olabilir)
    if len(messages) > 10:
        messages = [messages[0]] + messages[-9:]

    # Check for executed actions in conversation history
    executed_actions = []
    for msg in messages:
        if msg.get('role') == 'assistant':
            content = msg.get('content', '')
            if 'oluşturuldu' in content or 'güncellendi' in content or 'yapıldı' in content:
                executed_actions.append(content)

    system = SYSTEM_PROMPT + ACTION_SYSTEM
    if context:
        system += "\n\nMevcut bağlam:\n"
        for k, v in sanitize_context(context).items():
            system += f"- {k}: {v}\n"
    
    if executed_actions:
        system += "\n\nDaha önce yapılan aksiyonlar (TEKRAR ÖNERME):\n"
        for action in executed_actions[-3:]:  # Son 3 aksiyon
            system += f"- {action}\n"

    try:
        response_text = ''
        workspace_id = session.get('workspace_id')
        ai = _get_workspace_ai(workspace_id)

        # Sağlayıcı fallback sırası: Groq -> Anthropic -> Gemini -> OpenRouter
        provider_attempted = False
        provider_errors = []

        if ai['groq_key'] and ai['groq_client']:
            provider_attempted = True
            try:
                resp = ai['groq_client'].chat.completions.create(
                    model=ai['groq_model'],
                    messages=([{'role': 'system', 'content': system}] if system else []) + messages,
                    max_tokens=512,
                    temperature=0.7,
                )
                response_text = resp.choices[0].message.content
            except Exception as e:
                provider_errors.append(('groq', e))

        if not response_text and ai['anthropic_key'] and ai['anthropic_client']:
            provider_attempted = True
            try:
                resp = ai['anthropic_client'].messages.create(
                    model=ai['anthropic_model'],
                    max_tokens=512,  # 1024'ten 512'ye düşürüldü
                    system=system,
                    messages=messages
                )
                response_text = resp.content[0].text
            except Exception as e:
                provider_errors.append(('anthropic', e))

        if not response_text and ai['gemini_key'] and ai['gemini_client']:
            provider_attempted = True
            try:
                gemini_messages = [
                    {'role': 'user' if m['role'] == 'user' else 'model',
                     'parts': [m['content']]}
                    for m in messages
                ]
                if system:
                    gemini_messages.insert(0, {'role': 'user', 'parts': [system]})

                model = ai['gemini_client'].GenerativeModel(ai['gemini_model'])
                resp = model.generate_content(gemini_messages)
                response_text = resp.text
            except Exception as e:
                provider_errors.append(('gemini', e))

        if not response_text and ai['openrouter_key']:
            provider_attempted = True
            try:
                headers = {
                    'Authorization': f"Bearer {ai['openrouter_key']}",
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://whatsapp-crm-saas.onrender.com',
                }
                payload = {
                    'model': ai['openrouter_model'],
                    'messages': ([{'role': 'system', 'content': system}] if system else []) + messages,
                    'max_tokens': 512,  # 1024'ten 512'ye düşürüldü
                }
                resp = requests.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
                # Bazı modeller OpenRouter tarafında kaldırılmış olabilir; 404'te auto modele fallback yap.
                if resp.status_code == 404 and ai['openrouter_model'] != 'openrouter/auto':
                    payload['model'] = 'openrouter/auto'
                    resp = requests.post(
                        'https://openrouter.ai/api/v1/chat/completions',
                        headers=headers,
                        json=payload,
                        timeout=30,
                    )

                resp.raise_for_status()
                data = resp.json()
                response_text = data['choices'][0]['message']['content']
            except requests.exceptions.HTTPError as e:
                provider_errors.append(('openrouter', e))
                if e.response is not None and e.response.status_code == 429:
                    return jsonify({
                        'error': 'OpenRouter için istek limiti aşıldı (429). Lütfen kısa süre bekleyip tekrar deneyin veya farklı bir AI sağlayıcısı etkinleştirin.'
                    }), 429
                if e.response is not None and e.response.status_code == 404:
                    return jsonify({
                        'error': 'OpenRouter modeli bulunamadı (404). AI Ayarları > OpenRouter modelini `openrouter/auto` yapıp tekrar deneyin.'
                    }), 400
            except Exception as e:
                provider_errors.append(('openrouter', e))

        if not response_text and not provider_attempted:
            return jsonify({'error': 'API anahtarı bulunamadı. Ayarlar > AI Ayarları bölümünden API anahtarınızı ekleyin.'}), 500

        if not response_text and provider_errors:
            provider_name, provider_error = provider_errors[-1]
            return jsonify({'error': f'{provider_name} sağlayıcısı yanıt veremedi: {str(provider_error)}'}), 500

        # Markdown code fence'leri temizle (agresif)
        clean = response_text.strip()
        
        # Tüm markdown fence'leri kaldır
        if '```' in clean:
            # İlk ``` sonrasını al
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1] if '\n' in clean else clean[3:]
            # Son ``` öncesini al
            if '```' in clean:
                clean = clean.rsplit('```', 1)[0]
            clean = clean.strip()
        
        # "json" kelimesini baştan kaldır
        if clean.lower().startswith('json'):
            clean = clean[4:].strip()

        # JSON aksiyon mı? (Daha agresif parse)
        try:
            # Önce direkt parse dene
            parsed = json_lib.loads(clean)
            if isinstance(parsed, dict) and parsed.get('requires_confirmation'):
                return jsonify(parsed)
        except (json_lib.JSONDecodeError, ValueError):
            # JSON bulunamadı, text içinde JSON ara
            import re
            json_match = re.search(r'\{[^{}]*"requires_confirmation"[^{}]*\}', clean)
            if json_match:
                try:
                    parsed = json_lib.loads(json_match.group(0))
                    if isinstance(parsed, dict) and parsed.get('requires_confirmation'):
                        return jsonify(parsed)
                except:
                    pass

        return jsonify({'response': response_text})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

EXCLUDED_FIELDS = ['password_hash', 'api_key', 'access_token', 
                   'refresh_token', 'secret_key', 'webhook_secret']

def sanitize_context(ctx: dict) -> dict:
    result = {}
    for i, (k, v) in enumerate(ctx.items()):
        if i >= 20:
            break
        if k in EXCLUDED_FIELDS:
            continue
        result[k] = str(v)[:200] if v else ''
    return result

@bp.route('/api/ai/context/deal/<int:deal_id>', methods=['GET'])
@login_required
@require_app('ai_assistant')
def get_deal_context(deal_id):
    """Deal için zengin bağlam verisi topla."""
    workspace_id = session.get('workspace_id')
    deal = Deal.query.filter_by(
        id=deal_id,
        workspace_id=workspace_id
    ).first_or_404()

    context = {
        'deal_adi': deal.name,
        'deger': f"{deal.value} TL" if deal.value else 'Belirtilmemiş',
        'durum': deal.status,
        'asama': deal.stage.name if deal.stage else 'Belirtilmemiş',
        'beklenen_kapanis': deal.expected_close_date.strftime('%d.%m.%Y') if deal.expected_close_date else 'Belirtilmemiş',
        'sonraki_adim': deal.next_step or 'Belirtilmemiş',
    }

    if deal.company:
        context['sirket'] = deal.company.name
        context['sirket_sektoru'] = getattr(deal.company, 'industry', '') or ''

    if deal.primary_contact:
        c = deal.primary_contact
        context['ilgili_kisi'] = c.full_name
        context['ilgili_kisi_email'] = c.email or ''
        context['ilgili_kisi_telefon'] = c.phone or ''

    # Son aktiviteleri ekle
    try:
        recent_convs = Conversation.query.filter_by(
            workspace_id=workspace_id
        ).order_by(Conversation.last_message_at.desc()).limit(3).all()

        if recent_convs:
            conv_summaries = []
            for conv in recent_convs:
                last_msg = Message.query.filter_by(
                    conversation_id=conv.id
                ).order_by(Message.created_at.desc()).first()
                if last_msg:
                    conv_summaries.append(f"{conv.profile_name}: {last_msg.message_body[:100]}")
            if conv_summaries:
                context['son_konusmalar'] = ' | '.join(conv_summaries)
    except Exception:
        pass

    return jsonify({'context': sanitize_context(context)})

@bp.route('/api/ai/context/contact/<int:contact_id>', methods=['GET'])
@login_required
@require_app('ai_assistant')
def get_contact_context(contact_id):
    """Contact için zengin bağlam verisi topla."""
    workspace_id = session.get('workspace_id')
    contact = Contact.query.filter_by(
        id=contact_id,
        workspace_id=workspace_id
    ).first_or_404()

    context = {
        'kisi_adi': contact.full_name,
        'email': contact.email or 'Belirtilmemiş',
        'telefon': contact.phone or 'Belirtilmemiş',
        'pozisyon': getattr(contact, 'job_title', '') or 'Belirtilmemiş',
    }

    if contact.company:
        context['sirket'] = contact.company.name

    # Bu kişiye ait açık deal'lar
    try:
        deals = Deal.query.filter_by(
            primary_contact_id=contact_id,
            workspace_id=workspace_id
        ).limit(5).all()
        if deals:
            context['acik_deallar'] = ', '.join(
                f"{d.name} ({d.value} TL)" for d in deals
            )
    except Exception:
        pass

    return jsonify({'context': sanitize_context(context)})

@bp.route('/api/ai/context/company/<int:company_id>', methods=['GET'])
@login_required
@require_app('ai_assistant')
def get_company_context(company_id):
    """Company için zengin bağlam verisi topla."""
    workspace_id = session.get('workspace_id')
    company = Company.query.filter_by(
        id=company_id,
        workspace_id=workspace_id
    ).first_or_404()

    context = {
        'sirket_adi': company.name,
        'sektor': company.industry or 'Belirtilmemiş',
        'calisan_sayisi': company.employee_count or 'Belirtilmemiş',
        'websitesi': company.website or 'Belirtilmemiş',
        'adres': company.address or 'Belirtilmemiş'
    }

    # Bu şirkete ait kişiler
    try:
        contacts = Contact.query.filter_by(
            company_id=company_id,
            workspace_id=workspace_id
        ).limit(5).all()
        if contacts:
            context['sirket_kisileri'] = ', '.join(
                f"{c.full_name} ({c.job_title or 'Pozisyon yok'})" for c in contacts
            )
    except Exception:
        pass

    # Bu şirkete ait deal'lar
    try:
        deals = Deal.query.filter_by(
            company_id=company_id,
            workspace_id=workspace_id
        ).limit(5).all()
        if deals:
            context['sirket_deallari'] = ', '.join(
                f"{d.name} ({d.value} TL)" for d in deals
            )
    except Exception:
        pass

    return jsonify({'context': sanitize_context(context)})

@bp.route('/api/ai/summarize', methods=['POST'])
@login_required
@require_app('ai_assistant')
def summarize():
    """Konuşma geçmişini özetle."""
    data = request.get_json()
    messages_text = data.get('messages_text', '')

    if not messages_text:
        return jsonify({'error': 'Konuşma metni gerekli'}), 400

    prompt = f"""Aşağıdaki müşteri konuşmasını özetle. Şu başlıkları kullan:
- Ana konu
- Müşteri talebi
- Yapılan işlemler
- Sonraki adım

Konuşma:
{messages_text}"""

    return _call_ai([{'role': 'user', 'content': prompt}])

@bp.route('/api/ai/draft-email', methods=['POST'])
@login_required
@require_app('ai_assistant')
def draft_email():
    data = request.get_json()
    context = data.get('context', {})
    email_type = data.get('email_type', 'followup')

    email_types = {
        'followup': 'takip e-postası',
        'proposal': 'teklif sunumu e-postası',
        'thankyou': 'teşekkür e-postası',
        'reminder': 'ödeme hatırlatma e-postası',
    }

    # Gereksiz tekrar eden alanları temizle
    clean_context = {
        'Müşteri': context.get('ilgili_kisi') or context.get('İlgili kişi', ''),
        'Email': context.get('ilgili_kisi_email', ''),
        'Şirket': context.get('sirket') or context.get('Şirket', ''),
        'Deal': context.get('deal_adi') or context.get('Deal adı', ''),
        'Değer': context.get('deger') or context.get('Değer', ''),
        'Aşama': context.get('asama', ''),
        'Durum': context.get('durum') or context.get('Durum', ''),
        'Sonraki adım': context.get('sonraki_adim', ''),
    }

    context_text = '\n'.join(
        f"- {k}: {v}" for k, v in clean_context.items() if v and v != 'Belirtilmemiş'
    )

    prompt = f"""Aşağıdaki CRM bilgilerini kullanarak profesyonel bir {email_types.get(email_type, 'takip e-postası')} yaz.

CRM Verisi:
{context_text}

Kurallar:
- Hemen e-postayı yaz, bilgi sorma
- Konu satırıyla başla (Konu: ...)
- Müşterinin adını ve şirketini kullan
- Türkçe, profesyonel ve samimi ton
- Maksimum 150 kelime"""

    return _call_ai([{'role': 'user', 'content': prompt}])

@bp.route('/api/ai/suggest-reply', methods=['POST'])
@login_required
@require_app('ai_assistant')
def suggest_reply():
    """Müşteri mesajına cevap öner."""
    data = request.get_json()
    customer_message = data.get('customer_message', '')
    context = data.get('context', {})

    if not customer_message:
        return jsonify({'error': 'Müşteri mesajı gerekli'}), 400

    prompt = f"""Müşteri şunu yazdı:
"{customer_message}"

Bağlam: {context}

Bu mesaja 3 farklı cevap öner:
1. Kısa ve direkt
2. Detaylı ve açıklayıcı  
3. Empati kurarak

Her birini numaralandır."""

    return _call_ai([{'role': 'user', 'content': prompt}])

@bp.route('/api/ai/deal-score/<int:deal_id>', methods=['GET'])
@login_required
@require_app('ai_assistant')
def deal_score(deal_id):
    """Deal kapanma skoru ve analiz üret."""
    from models import db
    from sqlalchemy import func
    from datetime import datetime
    
    workspace_id = session.get('workspace_id')
    deal = Deal.query.filter_by(
        id=deal_id,
        workspace_id=workspace_id
    ).first_or_404()

    # Workspace genelindeki kazanılan/kaybedilen deal ortalamaları
    won_avg = db.session.query(func.avg(Deal.value)).filter_by(
        workspace_id=workspace_id,
        status='won'
    ).scalar() or 0

    context = {
        'deal_adi': deal.name,
        'deger': deal.value or 0,
        'asama': deal.stage.name if getattr(deal, 'stage', None) else 'Bilinmiyor',
        'durum': deal.status,
        'beklenen_kapanis': deal.expected_close_date.strftime('%d.%m.%Y') if deal.expected_close_date else 'Belirtilmemiş',
        'sonraki_adim': deal.next_step or 'Tanımlanmamış',
        'sirket': deal.company.name if deal.company else 'Belirtilmemiş',
        'ilgili_kisi': deal.primary_contact.full_name if deal.primary_contact else 'Belirtilmemiş',
        'kazanilan_deal_ortalama_degeri': round(won_avg, 2),
        'gun_sayisi': (datetime.utcnow() - deal.created_at).days if deal.created_at else 0,
    }

    context_text = '\n'.join(f"- {k}: {v}" for k, v in context.items())

    prompt = f"""Aşağıdaki CRM verisine göre bu deal için bir analiz yap.

Deal Verisi:
{context_text}

Şu formatta yanıt ver:

SKOR: [0-100 arası bir sayı]
DURUM: [Yüksek / Orta / Düşük risk]
GÜÇLÜ YÖNLER:
- [madde]
- [madde]
RİSKLER:
- [madde]
- [madde]
ÖNERİLER:
- [madde]
- [madde]
ÖZET: [1-2 cümle]"""

    return _call_ai([{'role': 'user', 'content': prompt}])


@bp.route('/api/ai/customer-analysis/<int:contact_id>', methods=['GET'])
@login_required
@require_app('ai_assistant')
def customer_analysis(contact_id):
    """Müşteri profili ve davranış analizi."""
    workspace_id = session.get('workspace_id')
    contact = Contact.query.filter_by(
        id=contact_id,
        workspace_id=workspace_id
    ).first_or_404()

    # Bu müşteriye ait tüm deal'ları çek
    deals = Deal.query.filter_by(
        contact_id=contact_id,
        workspace_id=workspace_id
    ).all()

    total_value = sum(d.value or 0 for d in deals)
    won_deals = [d for d in deals if d.status == 'won']
    lost_deals = [d for d in deals if d.status == 'lost']
    open_deals = [d for d in deals if d.status == 'open']

    context = {
        'musteri_adi': contact.full_name,
        'sirket': contact.company.name if contact.company else 'Belirtilmemiş',
        'pozisyon': getattr(contact, 'job_title', '') or 'Belirtilmemiş',
        'toplam_deal_sayisi': len(deals),
        'kazanilan_deal': len(won_deals),
        'kaybedilen_deal': len(lost_deals),
        'acik_deal': len(open_deals),
        'toplam_deger': f"{total_value:,.0f} TL",
        'kazanma_orani': f"{(len(won_deals)/len(deals)*100):.0f}%" if deals else "0%",
    }

    if open_deals:
        context['acik_deallar'] = ', '.join(
            f"{d.name} ({d.value or 0:,.0f} TL)" for d in open_deals[:3]
        )

    context_text = '\n'.join(f"- {k}: {v}" for k, v in context.items())

    prompt = f"""Aşağıdaki müşteri verisine göre kapsamlı bir profil analizi yap.

Müşteri Verisi:
{context_text}

Şu formatta yanıt ver:

MÜŞTERİ PROFİLİ: [2-3 cümle genel değerlendirme]
POTANSİYEL DEĞERİ: [Yüksek / Orta / Düşük]
FIRSAT ALANLARI:
- [madde]
- [madde]
DİKKAT EDİLMESİ GEREKENLER:
- [madde]
SONRAKİ ADIM ÖNERİSİ: [somut bir öneri]"""

    return _call_ai([{'role': 'user', 'content': prompt}])


@bp.route('/api/ai/pipeline-insights', methods=['GET'])
@login_required
@require_app('ai_assistant')
def pipeline_insights():
    """Pipeline geneli için haftalık insight üret."""
    from models import db
    from sqlalchemy import func
    from models_crm import DealStage

    workspace_id = session.get('workspace_id')

    # Temel istatistikler
    total_open = Deal.query.filter_by(workspace_id=workspace_id, status='open').count()
    total_won = Deal.query.filter_by(workspace_id=workspace_id, status='won').count()
    total_lost = Deal.query.filter_by(workspace_id=workspace_id, status='lost').count()

    open_value = db.session.query(func.sum(Deal.value)).filter_by(
        workspace_id=workspace_id, status='open'
    ).scalar() or 0

    won_value = db.session.query(func.sum(Deal.value)).filter_by(
        workspace_id=workspace_id, status='won'
    ).scalar() or 0

    # Aşamalara göre dağılım
    stages = db.session.query(
        DealStage.name,
        func.count(Deal.id)
    ).join(Deal, Deal.stage_id == DealStage.id)\
     .filter(Deal.workspace_id == workspace_id, Deal.status == 'open')\
     .group_by(DealStage.name).all()

    stage_dist = ', '.join(f"{s[0]}: {s[1]} deal" for s in stages)
    
    win_rate = f"{(total_won/(total_won+total_lost)*100):.0f}%" if total_won+total_lost > 0 else "0%"

    context_text = f"""- Açık deal sayısı: {total_open}
- Kazanılan deal: {total_won}
- Kaybedilen deal: {total_lost}
- Kazanma oranı: {win_rate}
- Açık pipeline değeri: {open_value:,.0f} TL
- Toplam kazanılan değer: {won_value:,.0f} TL
- Aşama dağılımı: {stage_dist or 'Veri yok'}"""

    prompt = f"""Aşağıdaki CRM pipeline verisini analiz et ve haftalık bir yönetici özeti hazırla.

Pipeline Verisi:
{context_text}

Şu formatta yanıt ver:

GENEL DURUM: [1-2 cümle]
GÜÇLÜ YÖNLER:
- [madde]
RİSKLER:
- [madde]
BU HAFTA ODAKLANILMASI GEREKENLER:
- [madde]
- [madde]
TAHMİN: [Bu ay kapanması beklenen deal sayısı ve değeri tahmini]"""

    return _call_ai([{'role': 'user', 'content': prompt}])

def _call_ai(messages, system=None, provider=None):
    """Ortak AI çağrı fonksiyonu."""
    import logging
    logger = logging.getLogger(__name__)
    
    system_prompt = system or SYSTEM_PROMPT
    workspace_id = session.get('workspace_id')
    ai = _get_workspace_ai(workspace_id)

    if provider is None:
        # Priority: Groq > OpenRouter > Gemini > Anthropic
        if ai['groq_key']:
            provider = 'groq'
        elif ai['openrouter_key']:
            provider = 'openrouter'
        elif ai['gemini_key']:
            provider = 'gemini'
        else:
            provider = 'anthropic'
    
    logger.info(f"[AI] _call_ai - Provider: {provider}, OpenRouter key exists: {bool(ai.get('openrouter_key'))}, Model: {ai.get('openrouter_model')}")
    
    if ai.get('openrouter_key'):
        logger.info(f"[AI] OpenRouter key length: {len(ai['openrouter_key'])}")
    else:
        logger.warning(f"[AI] OpenRouter key is None or empty!")

    try:
        if provider == 'openrouter' and ai['openrouter_key']:
            # OpenRouter HTTP API
            try:
                headers = {
                    'Authorization': f"Bearer {ai['openrouter_key']}",
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://whatsapp-crm-saas.onrender.com',
                }
                payload = {
                    'model': ai['openrouter_model'],
                    'messages': [{'role': 'system', 'content': system_prompt}] + messages if system_prompt else messages,
                    'max_tokens': 512,
                }
                logger.info(f"[OpenRouter] Sending request to OpenRouter API, model={ai['openrouter_model']}")
                response = requests.post('https://openrouter.ai/api/v1/chat/completions', 
                                        headers=headers, json=payload, timeout=30)
                logger.info(f"[OpenRouter] Status: {response.status_code}")
                response.raise_for_status()
                data = response.json()
                logger.info(f"[OpenRouter] Response received: {str(data)[:200]}")
                return jsonify({'response': data['choices'][0]['message']['content']})
            except Exception as openrouter_error:
                logger.error(f"[OpenRouter] Error: {str(openrouter_error)}")
                import traceback
                logger.error(f"[OpenRouter] Traceback: {traceback.format_exc()}")
                raise
            
        elif provider == 'gemini' and ai['gemini_client']:
            gemini_messages = []
            for msg in messages:
                role = 'user' if msg['role'] == 'user' else 'model'
                gemini_messages.append({'role': role, 'parts': [msg['content']]})
            
            if system_prompt:
                gemini_messages.insert(0, {'role': 'user', 'parts': [system_prompt]})
            
            model = ai['gemini_client'].GenerativeModel(ai['gemini_model'])
            response = model.generate_content(gemini_messages)
            return jsonify({'response': response.text})
            
        elif provider == 'groq' and ai['groq_client']:
            # Groq API
            try:
                groq_messages = [{'role': 'system', 'content': system_prompt}] + messages if system_prompt else messages
                response = ai['groq_client'].chat.completions.create(
                    model=ai['groq_model'],
                    messages=groq_messages,
                    max_tokens=1024,
                    temperature=0.7
                )
                return jsonify({'response': response.choices[0].message.content})
            except Exception as groq_error:
                logger.error(f"[Groq] Error: {str(groq_error)}")
                import traceback
                logger.error(f"[Groq] Traceback: {traceback.format_exc()}")
                raise
            
        elif provider == 'anthropic' and ai['anthropic_client']:
            response = ai['anthropic_client'].messages.create(
                model=ai['anthropic_model'],
                max_tokens=1024,
                system=system_prompt,
                messages=[{'role': m['role'], 'content': m['content']} for m in messages]
            )
            return jsonify({'response': response.content[0].text})
        else:
            return jsonify({'error': 'API anahtarı bulunamadı. Ayarlar > AI Ayarları bölümünden API anahtarınızı ekleyin.'}), 500
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


def _call_ai_raw(messages: list, system: str, workspace_id: int) -> str:
    """String döndüren AI çağrısı — enrichment için."""
    ai = _get_workspace_ai(workspace_id)
    if not ai:
        return ''

    try:
        # Priority: Groq > OpenRouter > Gemini > Anthropic
        if ai.get('groq_client'):
            groq_messages = [{'role': 'system', 'content': system}] + messages
            response = ai['groq_client'].chat.completions.create(
                model=ai['groq_model'],
                messages=groq_messages,
                max_tokens=256,
                temperature=0.3
            )
            return response.choices[0].message.content

        elif ai.get('openrouter_key'):
            headers = {
                'Authorization': f"Bearer {ai['openrouter_key']}",
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://whatsapp-crm-saas.onrender.com',
            }
            payload = {
                'model': ai['openrouter_model'],
                'messages': [{'role': 'system', 'content': system}] + messages,
                'max_tokens': 256,
            }
            response = requests.post('https://openrouter.ai/api/v1/chat/completions',
                                    headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']

        elif ai.get('gemini_client'):
            gemini_messages = []
            for msg in messages:
                role = 'user' if msg['role'] == 'user' else 'model'
                gemini_messages.append({'role': role, 'parts': [msg['content']]})

            model = ai['gemini_client'].GenerativeModel(ai['gemini_model'])
            response = model.generate_content(gemini_messages)
            return response.text

        elif ai.get('anthropic_client'):
            response = ai['anthropic_client'].messages.create(
                model=ai['anthropic_model'],
                max_tokens=256,
                system=system,
                messages=[{'role': m['role'], 'content': m['content']} for m in messages]
            )
            return response.content[0].text

        return ''

    except Exception as e:
        logger.error(f"[_call_ai_raw] Error: {e}")
        return ''



@bp.route('/api/ai/execute-action', methods=['POST'])
@login_required
@require_app('ai_assistant')
def execute_action():
    """Onaylanan AI aksiyonunu veritabanına uygula."""
    from models import db
    data = request.get_json()
    action = data.get('action', '')
    params = data.get('params', {})
    workspace_id = session.get('workspace_id')

    try:
        if action == 'create_contact':
            isim = params.get('isim', '').strip()
            if not isim:
                return jsonify({'error': 'İsim zorunlu'}), 400
            # full_name bir @property - first_name/last_name alanlarına böl
            parts = isim.split(' ', 1)
            contact = Contact(
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else '',
                email=params.get('email', ''),
                phone=params.get('telefon', ''),
                workspace_id=workspace_id
            )
            db.session.add(contact)
            db.session.commit()
            return jsonify({'message': f'"{isim}" adlı contact oluşturuldu.', 'id': contact.id})

        elif action == 'create_deal':
            isim = params.get('isim', '').strip()
            if not isim:
                return jsonify({'error': 'Deal adı zorunlu'}), 400
            deal = Deal(
                name=isim,
                value=float(params.get('deger', 0) or 0),
                status='open',
                workspace_id=workspace_id
            )
            db.session.add(deal)
            db.session.commit()
            return jsonify({'message': f'"{isim}" adlı deal oluşturuldu.', 'id': deal.id})

        elif action == 'update_deal_status':
            deal_id = params.get('deal_id')
            status = params.get('status', '').lower()
            if status not in ('won', 'lost', 'open'):
                return jsonify({'error': 'Geçersiz status (won/lost/open)'}), 400
            deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id).first_or_404()
            deal.status = status
            db.session.commit()
            return jsonify({'message': f'"{deal.name}" deal durumu "{status}" olarak güncellendi.'})

        elif action == 'update_contact':
            contact_id = params.get('contact_id')
            if not contact_id:
                # İsimle arama yap
                isim = params.get('isim', '').strip()
                if isim:
                    from sqlalchemy import or_, and_
                    parts = isim.split(' ', 1)
                    if len(parts) >= 2:
                        contact = Contact.query.filter(
                            Contact.workspace_id == workspace_id,
                            Contact.is_deleted == False,
                            and_(
                                Contact.first_name.ilike(f'%{parts[0]}%'),
                                Contact.last_name.ilike(f'%{parts[1]}%')
                            )
                        ).first()
                    else:
                        contact = Contact.query.filter(
                            Contact.workspace_id == workspace_id,
                            Contact.is_deleted == False,
                            or_(
                                Contact.first_name.ilike(f'%{parts[0]}%'),
                                Contact.last_name.ilike(f'%{parts[0]}%')
                            )
                        ).first()
                    if not contact:
                        return jsonify({'error': f'"{isim}" adlı contact bulunamadı.'}), 404
                else:
                    return jsonify({'error': 'contact_id veya isim gerekli'}), 400
            else:
                contact = Contact.query.filter_by(id=contact_id, workspace_id=workspace_id).first_or_404()

            updated_fields = []
            if params.get('email'):
                contact.email = params['email']
                updated_fields.append(f"email: {params['email']}")
            if params.get('telefon'):
                contact.phone = params['telefon']
                updated_fields.append(f"telefon: {params['telefon']}")
            if params.get('pozisyon'):
                contact.job_title = params['pozisyon']
                updated_fields.append(f"pozisyon: {params['pozisyon']}")
            if params.get('role'):
                contact.role = params['role']
                updated_fields.append(f"rol: {params['role']}")
            if params.get('sirket'):
                company = Company.query.filter(
                    Company.workspace_id == workspace_id,
                    Company.name.ilike(f"%{params['sirket']}%")
                ).first()
                if company:
                    contact.company_id = company.id
                    updated_fields.append(f"şirket: {company.name}")
                else:
                    updated_fields.append(f"şirket '{params['sirket']}' bulunamadı")
            if params.get('isim') and contact_id:
                parts = params['isim'].strip().split(' ', 1)
                contact.first_name = parts[0]
                contact.last_name = parts[1] if len(parts) > 1 else ''
                updated_fields.append(f"isim: {params['isim']}")

            if not updated_fields:
                return jsonify({'error': 'Güncellenecek alan belirtilmedi'}), 400

            db.session.commit()
            return jsonify({
                'message': f'"{contact.full_name}" güncellendi: {", ".join(updated_fields)}',
                'id': contact.id
            })

        elif action == 'update_deal_value':
            deal_id = params.get('deal_id')
            value = params.get('value')
            deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id).first_or_404()
            deal.value = float(value)
            db.session.commit()
            return jsonify({'message': f'"{deal.name}" deal değeri {float(value):,.0f} TL olarak güncellendi.'})

        else:
            return jsonify({'error': f'Bilinmeyen aksiyon: {action}'}), 400

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/ai/mention-search', methods=['GET'])
@login_required
@require_app('ai_assistant')
def mention_search():
    """@ mention için contact/deal/company ara."""
    q = request.args.get('q', '').strip()
    if len(q) < 1:
        return jsonify({'results': []})

    workspace_id = session.get('workspace_id')
    results = []

    # Contacts
    try:
        from sqlalchemy import or_
        contacts = Contact.query.filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
            or_(
                Contact.first_name.ilike(f'%{q}%'),
                Contact.last_name.ilike(f'%{q}%'),
                Contact.email.ilike(f'%{q}%')
            )
        ).limit(5).all()
        
        for c in contacts:
            results.append({
                'type': 'contact',
                'id': c.id,
                'name': c.full_name,
                'subtitle': c.email or c.phone or ''
            })
    except Exception:
        pass

    # Deals
    try:
        deals = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.is_deleted == False,
            Deal.name.ilike(f'%{q}%')
        ).limit(5).all()
        
        for d in deals:
            results.append({
                'type': 'deal',
                'id': d.id,
                'name': d.name,
                'subtitle': f"{d.value or 0:,.0f} TL - {d.stage.name if d.stage else ''}"
            })
    except Exception:
        pass

    # Companies
    try:
        companies = Company.query.filter(
            Company.workspace_id == workspace_id,
            Company.is_deleted == False,
            Company.name.ilike(f'%{q}%')
        ).limit(5).all()
        
        for comp in companies:
            results.append({
                'type': 'company',
                'id': comp.id,
                'name': comp.name,
                'subtitle': comp.industry or ''
            })
    except Exception:
        pass

    return jsonify({'results': results[:15]})


@bp.route('/api/ai/score-all', methods=['POST'])
@login_required
@require_app('ai_assistant')
def score_all():
    """Tüm açık deal'ları ve yüksek potansiyelli contact'ları skorla."""
    from services.ai_scoring_service import AIScoringService
    from models import db
    
    workspace_id = session.get('workspace_id')
    ai = _get_workspace_ai(workspace_id)
    
    if not (ai['gemini_client'] or ai['anthropic_client']):
        return jsonify({'error': 'AI API anahtarı bulunamadı'}), 500
    
    provider = 'anthropic' if ai['anthropic_client'] else 'gemini'
    client = ai['anthropic_client'] if provider == 'anthropic' else ai['gemini_client']
    model = ai['anthropic_model'] if provider == 'anthropic' else ai['gemini_model']
    
    # Açık deal'ları skorla
    deals = Deal.query.filter_by(
        workspace_id=workspace_id,
        status='open',
        is_deleted=False
    ).limit(50).all()
    
    scored_deals = 0
    for deal in deals:
        if AIScoringService.score_deal(deal, client, model, provider):
            scored_deals += 1
    
    # Yüksek potansiyelli contact'ları skorla (lead_score > 50 veya None)
    contacts = Contact.query.filter(
        Contact.workspace_id == workspace_id,
        Contact.is_deleted == False,
        db.or_(
            Contact.lead_score >= 50,
            Contact.lead_score.is_(None)
        )
    ).limit(50).all()
    
    scored_contacts = 0
    for contact in contacts:
        if AIScoringService.score_contact(contact, client, model, provider):
            scored_contacts += 1
    
    return jsonify({
        'message': f'{scored_deals} deal ve {scored_contacts} contact skorlandı',
        'deals': scored_deals,
        'contacts': scored_contacts
    })


@bp.route('/api/ai/daily-insights', methods=['GET'])
@login_required
@require_app('ai_assistant')
def daily_insights():
    """Günlük proaktif insight'lar - hareketsiz deal'lar, hot/cold deals, negative sentiment."""
    from services.ai_scoring_service import AIScoringService
    
    workspace_id = session.get('workspace_id')
    insights = AIScoringService.get_daily_insights(workspace_id)
    
    return jsonify(insights)


@bp.route('/api/ai/conversation-summary/<int:conversation_id>', methods=['POST'])
@login_required
@require_app('ai_assistant')
def conversation_summary(conversation_id):
    """Bir konuşmayı özetle ve sentiment analizi yap."""
    from services.ai_scoring_service import AIScoringService
    
    workspace_id = session.get('workspace_id')
    conversation = Conversation.query.filter_by(
        id=conversation_id,
        workspace_id=workspace_id
    ).first_or_404()
    
    ai = _get_workspace_ai(workspace_id)
    
    if not (ai['gemini_client'] or ai['anthropic_client']):
        return jsonify({'error': 'AI API anahtarı bulunamadı'}), 500
    
    provider = 'anthropic' if ai['anthropic_client'] else 'gemini'
    client = ai['anthropic_client'] if provider == 'anthropic' else ai['gemini_client']
    model = ai['anthropic_model'] if provider == 'anthropic' else ai['gemini_model']
    
    success = AIScoringService.summarize_conversation(conversation, client, model, provider)
    
    if success:
        return jsonify({
            'summary': conversation.ai_summary,
            'sentiment': conversation.ai_sentiment,
            'sentiment_score': conversation.ai_sentiment_score
        })
    else:
        return jsonify({'error': 'Özet oluşturulamadı'}), 500



@bp.route('/api/ai/quick-log', methods=['POST'])
@login_required
@require_app('ai_assistant')
def quick_log():
    """
    Quick Log — AI-powered multi-action CRM logging.
    User writes free text, AI extracts actions (note, task, deal update).
    Executes safe actions immediately, returns confirmation-required actions.
    """
    import logging
    from datetime import datetime, timedelta
    from models import db
    from models_crm import Task, Deal, DealStage, Pipeline, Contact
    from models_contact_timeline import ContactActivityLog
    
    logger = logging.getLogger(__name__)
    
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        context = data.get('context', {})
        
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Extract context IDs
        deal_id = context.get('deal_id')
        contact_id = context.get('contact_id')
        company_id = context.get('company_id')
        
        # Get pipeline stages for AI context
        pipeline_stages = []
        if deal_id:
            deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id).first()
            if deal and deal.pipeline_id:
                stages = DealStage.query.filter_by(
                    pipeline_id=deal.pipeline_id,
                    is_active=True
                ).order_by(DealStage.order).all()
                pipeline_stages = [{'name': s.name, 'order': s.order} for s in stages]
        
        # Build AI prompt
        prompt = f"""Analyze this CRM activity log and extract actionable items:

User input: "{text}"

Context:
- Deal ID: {deal_id or 'None'}
- Contact ID: {contact_id or 'None'}
- Company ID: {company_id or 'None'}
- Available pipeline stages: {', '.join([s['name'] for s in pipeline_stages]) if pipeline_stages else 'None'}

Extract actions from the text. Return JSON array with these action types:

1. create_contact: Create a new contact/customer
   - params: {{"name": "full name", "phone": "optional phone", "email": "optional email"}}
   - requires_confirmation: false
   - Use this when user wants to add/create a new customer/contact

2. add_note: Add a note/comment (requires existing contact/deal/company context)
   - params: {{"content": "note text"}}
   - requires_confirmation: false

3. create_task: Create a follow-up task
   - params: {{"title": "task title", "due_days": number_of_days_from_now, "contact_name": "optional contact name for linking"}}
   - requires_confirmation: false

4. update_deal_stage: Move deal to different stage
   - params: {{"stage_name": "exact stage name from available stages"}}
   - requires_confirmation: true

5. update_deal_status: Mark deal as won/lost
   - params: {{"status": "won" or "lost", "reason": "optional reason"}}
   - requires_confirmation: true

6. update_deal_value: Change deal value
   - params: {{"value": number}}
   - requires_confirmation: true

Return ONLY valid JSON in this exact format:
{{
  "actions": [
    {{"type": "create_contact", "params": {{"name": "...", "phone": "..."}}, "requires_confirmation": false}},
    {{"type": "create_task", "params": {{"title": "...", "due_days": 1, "contact_name": "..."}}, "requires_confirmation": false}},
    {{"type": "add_note", "params": {{"content": "..."}}, "requires_confirmation": false}}
  ],
  "summary": "Brief summary of what was detected"
}}

Rules:
- Only extract actions that are clearly mentioned or implied
- For tasks, estimate reasonable due_days (1-30)
- For stage updates, use exact stage names from available stages
- If no clear actions, return empty actions array
- Return ONLY the JSON, no markdown, no explanation"""

        # Call AI
        ai_response = _call_ai([{'role': 'user', 'content': prompt}])
        
        # _call_ai can return tuple (response, status_code) on error
        if isinstance(ai_response, tuple):
            return ai_response  # Return error tuple directly
        
        # _call_ai returns Flask Response, extract JSON
        if not ai_response:
            return jsonify({'error': 'AI service unavailable'}), 503
        
        # Get JSON data from Response object
        ai_data_raw = ai_response.get_json()
        if not ai_data_raw or 'response' not in ai_data_raw:
            return jsonify({'error': 'AI service unavailable'}), 503
        
        # Parse AI response
        import json
        import re
        
        response_text = ai_data_raw['response'].strip()
        # Remove markdown code blocks if present
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*$', '', response_text)
        response_text = response_text.strip()
        
        try:
            ai_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {response_text}")
            return jsonify({'error': 'Failed to parse AI response', 'details': str(e)}), 500
        
        actions = ai_data.get('actions', [])
        summary = ai_data.get('summary', 'Actions detected')
        
        # Execute actions
        executed_actions = []
        pending_confirmations = []
        
        for action in actions:
            action_type = action.get('type')
            params = action.get('params', {})
            requires_confirmation = action.get('requires_confirmation', False)
            
            result = {
                'type': action_type,
                'params': params,
                'requires_confirmation': requires_confirmation,
                'status': 'pending' if requires_confirmation else 'processing'
            }
            
            if requires_confirmation:
                pending_confirmations.append(result)
                continue
            
            # Execute safe actions immediately
            try:
                if action_type == 'create_contact':
                    name = params.get('name', '').strip()
                    phone = params.get('phone', '').strip()
                    email = params.get('email', '').strip()
                    
                    if name:
                        # Split name into first and last
                        name_parts = name.split(' ', 1)
                        first_name = name_parts[0]
                        last_name = name_parts[1] if len(name_parts) > 1 else ''
                        
                        contact = Contact(
                            workspace_id=workspace_id,
                            first_name=first_name,
                            last_name=last_name,
                            phone=phone or None,
                            email=email or None,
                            created_at=datetime.utcnow()
                        )
                        db.session.add(contact)
                        db.session.commit()
                        
                        # Store contact_id for subsequent actions
                        contact_id = contact.id
                        
                        result['status'] = 'completed'
                        result['message'] = f'Contact created: {name}'
                        result['contact_id'] = contact.id
                    else:
                        result['status'] = 'skipped'
                        result['message'] = 'No name provided for contact'
                
                elif action_type == 'add_note':
                    content = params.get('content', '')
                    # Use contact_id from context or newly created contact
                    if content and contact_id:
                        # Use ContactActivityLog for timeline
                        activity = ContactActivityLog(
                            workspace_id=workspace_id,
                            contact_id=contact_id,
                            user_id=user_id,
                            action_type='note_added',
                            description=content,
                            created_at=datetime.utcnow()
                        )
                        db.session.add(activity)
                        db.session.commit()
                        result['status'] = 'completed'
                        result['message'] = f'Note added: "{content[:50]}..."'
                    else:
                        result['status'] = 'skipped'
                        result['message'] = 'No content or contact_id for note'
                
                elif action_type == 'create_task':
                    title = params.get('title', '')
                    due_days = params.get('due_days', 7)
                    contact_name = params.get('contact_name', '').strip()
                    
                    # If contact_name provided, try to find or use newly created contact
                    task_contact_id = contact_id
                    if contact_name and not task_contact_id:
                        # Try to find contact by name
                        name_parts = contact_name.split(' ', 1)
                        first_name = name_parts[0]
                        last_name = name_parts[1] if len(name_parts) > 1 else ''
                        
                        found_contact = Contact.query.filter_by(
                            workspace_id=workspace_id,
                            first_name=first_name
                        ).filter(
                            (Contact.last_name == last_name) | (Contact.last_name == None)
                        ).first()
                        
                        if found_contact:
                            task_contact_id = found_contact.id
                    
                    if title:
                        due_date = datetime.utcnow() + timedelta(days=due_days)
                        # Set start_time to beginning of due date for calendar visibility
                        # Use UTC time but set to 9 AM local time equivalent
                        start_time = due_date.replace(hour=9, minute=0, second=0, microsecond=0)
                        end_time = due_date.replace(hour=10, minute=0, second=0, microsecond=0)
                        
                        task = Task(
                            workspace_id=workspace_id,
                            title=title,
                            description=f'Created from Quick Log: {text[:100]}',
                            assignee_id=user_id,
                            deal_id=deal_id,
                            contact_id=task_contact_id,
                            company_id=company_id,
                            due_date=due_date.date(),  # Store only date part
                            start_time=start_time,
                            end_time=end_time,
                            status='not_started',
                            priority='medium',
                            task_type='follow_up',  # Set task_type for calendar icon
                            reminder_enabled=True,  # Enable reminder by default
                            reminder_minutes_before=60,  # 1 hour before
                            reminder_method='whatsapp'  # Default to WhatsApp
                        )
                        db.session.add(task)
                        db.session.commit()
                        result['status'] = 'completed'
                        result['message'] = f'Task created: "{title}" — {due_days} days (reminder: 1h before)'
                    else:
                        result['status'] = 'skipped'
                        result['message'] = 'No title for task'
                
                else:
                    result['status'] = 'unknown'
                    result['message'] = f'Unknown action type: {action_type}'
                
                executed_actions.append(result)
                
            except Exception as e:
                logger.error(f"Failed to execute action {action_type}: {str(e)}")
                result['status'] = 'failed'
                result['message'] = str(e)
                executed_actions.append(result)
        
        return jsonify({
            'success': True,
            'summary': summary,
            'executed': executed_actions,
            'pending_confirmations': pending_confirmations
        })
        
    except Exception as e:
        logger.error(f"Quick log error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/ai/enrichment-log/<int:contact_id>', methods=['GET'])
@login_required
def enrichment_log(contact_id):
    """Contact için enrichment geçmişini döndür."""
    from models_crm import EnrichmentLog
    workspace_id = session.get('workspace_id')
    
    logs = EnrichmentLog.query.filter_by(
        contact_id=contact_id,
        workspace_id=workspace_id
    ).order_by(EnrichmentLog.created_at.desc()).limit(20).all()
    
    return jsonify([{
        'field': l.field_name,
        'old': l.old_value,
        'new': l.new_value,
        'source': l.source,
        'confidence': l.confidence,
        'date': l.created_at.isoformat()
    } for l in logs])
