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
        'minimax_key': None,
        'gemini_model': 'gemini-2.5-flash',
        'anthropic_model': 'claude-3-5-sonnet-latest',
        'groq_model': 'llama-3.1-70b-versatile',
        'openrouter_model': 'openrouter/auto',
        'minimax_model': 'MiniMax-M2.7',
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
            elif row.provider == 'minimax' and decrypted:
                result['minimax_key'] = decrypted
                if row.model_name:
                    result['minimax_model'] = row.model_name
                logger.info(f"[AI] Using workspace MiniMax key, model={result['minimax_model']}")
    except Exception as e:
        logger.error(f"[AI] Failed to load workspace AI settings: {e}")
    return result

SYSTEM_PROMPT = """You are a powerful CRM AI assistant with FULL access to the CRM database.
You can search, create, update, and analyze ALL CRM data.

RESPONSE RULES:
- Greetings ("hello"/"hi"/"thanks") → brief friendly Turkish reply
- Data questions (list, search, stats, details) → return {"action": "crm_query", ...} JSON
- Write operations (create, update, delete) → return action JSON with requires_confirmation
- Analysis/advice questions → answer directly in Turkish using context data
- Always respond in Turkish unless the user writes in another language
- Use context data when available to give specific, data-driven answers"""

ACTION_SYSTEM = """

You have access to the following CRM actions. Return ONLY valid JSON when performing an action.

═══════════════════════════════════════════════
SECTION 1: DATA QUERIES (requires_confirmation: false)
═══════════════════════════════════════════════
These read data and return results. Always use action "crm_query".

{"action": "crm_query", "query_type": "TYPE", "params": {PARAMS}}

Available query_types:
1. search_contacts: Search contacts
   params: {query, filters: {role, lifecycle_stage, company_name, lead_score_min}}
2. search_companies: Search companies
   params: {query, filters: {industry, size}}
3. search_deals: Search deals
   params: {query, filters: {status, stage_name, min_value, max_value}}
4. get_contact_detail: Get full contact info
   params: {contact_id OR name}
5. get_company_detail: Get full company info
   params: {company_id OR name}
6. get_deal_detail: Get full deal info
   params: {deal_id OR name}
7. list_tasks: List/filter tasks
   params: {status, assignee_name, priority, date_from, date_to, task_type}
8. list_activities: List recent activities
   params: {entity_type, entity_id, activity_type, limit}
9. list_notes: Search notes on records
   params: {query, entity_type, entity_id}
10. list_team_members: List workspace team
    params: {}
11. crm_stats: Get CRM dashboard statistics
    params: {}
12. pipeline_summary: Get pipeline stage breakdown
    params: {pipeline_id}
13. list_custom_fields: List custom field definitions
    params: {entity_type}
14. search_tags: Search available tags
    params: {query}

═══════════════════════════════════════════════
SECTION 2: WRITE ACTIONS (requires_confirmation varies)
═══════════════════════════════════════════════

{"requires_confirmation": true/false, "action": "ACTION_NAME", "params": {PARAMS}, "message": "Turkish message"}

── Records ──
- create_contact: {isim, email, telefon, sirket, pozisyon, role, lead_source}
  requires_confirmation: true
- update_contact: {isim OR contact_id, ...fields to update: email/telefon/role/pozisyon/sirket/lead_source/lifecycle_stage}
  requires_confirmation: true
- create_company: {name, industry, size, website, email, phone, address}
  requires_confirmation: true
- update_company: {name OR company_id, ...fields to update}
  requires_confirmation: true
- create_deal: {isim, deger, sirket, contact_name, stage_name, expected_close_date}
  requires_confirmation: true
- update_deal_status: {deal_id OR deal_name, status: won/lost/open, reason}
  requires_confirmation: true
- update_deal_value: {deal_id OR deal_name, value}
  requires_confirmation: true
- update_deal_stage: {deal_id OR deal_name, stage_name}
  requires_confirmation: true
- delete_record: {entity_type: contact/company/deal, entity_id OR name}
  requires_confirmation: true

── Notes ──
- add_note: {entity_type: contact/company/deal, entity_id OR entity_name, content, note_type: note/call/meeting/email}
  requires_confirmation: false
- update_note: {note_id, content, mode: replace/append/prepend}
  requires_confirmation: true

── Tasks ──
- create_task: {title, description, assignee_name, due_date, priority: low/medium/high/urgent, task_type: call/meeting/email/todo/follow_up, contact_name, deal_name, company_name}
  requires_confirmation: false
- update_task: {task_id OR title, status: not_started/in_progress/completed/cancelled, priority, assignee_name}
  requires_confirmation: true
- complete_task: {task_id OR title}
  requires_confirmation: false

── Email ──
- draft_email: {to_email, to_name, subject, body, email_type: followup/proposal/thankyou/reminder}
  requires_confirmation: true (shows draft for review)

── Meetings ──
- create_meeting: {title, start_time, end_time, description, contact_name, deal_name}
  requires_confirmation: true

═══════════════════════════════════════════════
SECTION 3: IMPORTANT RULES
═══════════════════════════════════════════════

1. Return ONLY JSON for actions. NO markdown, NO explanation, NO extra text.
2. For data queries, ALWAYS use action "crm_query" with the appropriate query_type.
3. Extract real names from context or user message — NO placeholders.
4. "role" = Decision Maker, Influencer, Champion, Blocker, End User (business role)
5. "pozisyon" = job title like CEO, Manager, Engineer
6. When user asks to "list" or "show" or "search" or "find" → use crm_query
7. When user asks to "create" or "add" or "update" or "change" or "delete" → use write action
8. For ambiguous requests, prefer showing data first before modifying
9. Dates should be in YYYY-MM-DD format
10. When searching by name, use the name as provided by the user

EXAMPLES:
User: "Tüm açık deal'ları göster"
→ {"action": "crm_query", "query_type": "search_deals", "params": {"filters": {"status": "open"}}}

User: "Ahmet Yılmaz'a bir not ekle: Toplantı olumlu geçti"
→ {"action": "add_note", "requires_confirmation": false, "params": {"entity_type": "contact", "entity_name": "Ahmet Yılmaz", "content": "Toplantı olumlu geçti", "note_type": "note"}, "message": "Ahmet Yılmaz'a not eklendi"}

User: "Yarın için Mehmet'i ara görevi oluştur"
→ {"action": "create_task", "requires_confirmation": false, "params": {"title": "Mehmet'i ara", "task_type": "call", "contact_name": "Mehmet", "due_date": "TOMORROW_DATE", "priority": "medium"}, "message": "Görev oluşturuldu: Mehmet'i ara"}

User: "Ekip üyelerini listele"
→ {"action": "crm_query", "query_type": "list_team_members", "params": {}}

User: "CRM istatistiklerini ver"
→ {"action": "crm_query", "query_type": "crm_stats", "params": {}}

User: "ABC Teknoloji şirketini oluştur, sektörü yazılım"
→ {"requires_confirmation": true, "action": "create_company", "params": {"name": "ABC Teknoloji", "industry": "Yazılım"}, "message": "ABC Teknoloji şirketi oluşturulacak"}
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

        # Sağlayıcı fallback sırası: Groq -> Anthropic -> Gemini -> OpenRouter -> MiniMax
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
                    max_tokens=2048,
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
                    'max_tokens': 2048,
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

        if not response_text and ai['minimax_key']:
            provider_attempted = True
            try:
                headers = {
                    'Authorization': f"Bearer {ai['minimax_key']}",
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                }
                minimax_messages = ([{'role': 'system', 'content': system}] if system else []) + messages
                payload = {
                    'model': ai['minimax_model'],
                    'max_tokens': 2048,
                    'messages': [{'role': m['role'], 'content': m['content']} for m in minimax_messages]
                }
                resp = requests.post(
                    'https://api.minimax.io/anthropic/v1/messages',
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                # MiniMax returns Anthropic-compatible format with content blocks
                # Response may contain multiple blocks (thinking, text, etc.)
                # Iterate through ALL blocks to find type='text'
                if data.get('content') and isinstance(data['content'], list):
                    thinking_fallback = ''
                    for content_block in data['content']:
                        if isinstance(content_block, dict):
                            if content_block.get('type') == 'text':
                                text_content = content_block.get('text', '')
                                if text_content:
                                    response_text = text_content
                                    break
                            elif content_block.get('type') == 'thinking':
                                thinking_fallback = content_block.get('thinking', '')
                    
                    if not response_text and thinking_fallback:
                        response_text = "*(Model yanıtı bitiremedi)*\n\nDüşünme süreci:\n" + thinking_fallback
            except Exception as e:
                provider_errors.append(('minimax', e))

        if not response_text and not provider_attempted:
            return jsonify({'error': 'API anahtarı bulunamadı. Ayarlar > AI Ayarları bölümünden API anahtarınızı ekleyin.'}), 500

        if not response_text and provider_errors:
            provider_name, provider_error = provider_errors[-1]
            return jsonify({'error': f'{provider_name} sağlayıcısı yanıt veremedi: {str(provider_error)}'}), 500

        # Markdown code fence'leri temizle (agresif)
        clean = response_text.strip()
        
        # Tüm markdown fence'leri kaldır
        if '```' in clean:
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1] if '\n' in clean else clean[3:]
            if '```' in clean:
                clean = clean.rsplit('```', 1)[0]
            clean = clean.strip()
        
        # "json" kelimesini baştan kaldır
        if clean.lower().startswith('json'):
            clean = clean[4:].strip()

        # JSON aksiyon mı? (Agresif parse)
        try:
            parsed = json_lib.loads(clean)
            if isinstance(parsed, dict):
                # CRM Query — tool-use pattern: execute query, feed results back to AI
                if parsed.get('action') == 'crm_query':
                    query_result = _execute_crm_query(parsed.get('query_type', ''), parsed.get('params', {}), session.get('workspace_id'))
                    # Feed query results back to AI for natural language response
                    followup_messages = messages + [
                        {'role': 'assistant', 'content': clean},
                        {'role': 'user', 'content': f'İşte sorgunun sonuçları (bu verileri kullanarak TÜRKÇE doğal dilde yanıt ver, JSON döndürme):\n{json_lib.dumps(query_result, ensure_ascii=False, default=str)[:3000]}'}
                    ]
                    followup_system = "Sen bir CRM asistanısın. Sana verilen CRM verilerini güzel formatlayarak Türkçe olarak kullanıcıya sun. Tablo formatı veya madde işaretleri kullan. Kısa ve öz ol. JSON döndürme, sadece düz metin yaz."
                    # Call AI again for natural language formatting
                    try:
                        nl_response = _call_ai_raw(followup_messages[-4:], followup_system, session.get('workspace_id'))
                        if nl_response:
                            return jsonify({'response': nl_response})
                    except Exception:
                        pass
                    # Fallback: return raw data formatted
                    return jsonify({'response': _format_query_result(query_result)})
                
                # Write action with confirmation
                if parsed.get('requires_confirmation') is not None:
                    return jsonify(parsed)
                
                # Auto-execute actions without confirmation
                if parsed.get('action') in ('add_note', 'create_task', 'complete_task'):
                    exec_result = _auto_execute_action(parsed.get('action'), parsed.get('params', {}), session.get('workspace_id'), session.get('user_id'))
                    return jsonify({'response': exec_result})
        except (json_lib.JSONDecodeError, ValueError):
            import re
            # Try to find crm_query JSON
            json_match = re.search(r'\{[^{}]*"action"\s*:\s*"crm_query"[^{}]*\}', clean)
            if not json_match:
                json_match = re.search(r'\{[^{}]*"requires_confirmation"[^{}]*\}', clean)
            if not json_match:
                # Try to find any JSON with "action" key
                json_match = re.search(r'\{[^{}]*"action"\s*:[^{}]*\}', clean)
            if json_match:
                try:
                    parsed = json_lib.loads(json_match.group(0))
                    if isinstance(parsed, dict):
                        if parsed.get('action') == 'crm_query':
                            query_result = _execute_crm_query(parsed.get('query_type', ''), parsed.get('params', {}), session.get('workspace_id'))
                            return jsonify({'response': _format_query_result(query_result)})
                        if parsed.get('requires_confirmation') is not None:
                            return jsonify(parsed)
                        if parsed.get('action') in ('add_note', 'create_task', 'complete_task'):
                            exec_result = _auto_execute_action(parsed.get('action'), parsed.get('params', {}), session.get('workspace_id'), session.get('user_id'))
                            return jsonify({'response': exec_result})
                except:
                    pass

        return jsonify({'response': response_text})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════════════════════════
# CRM QUERY ENGINE — handles all read operations from AI
# ════════════════════════════════════════════════════════════════

def _execute_crm_query(query_type, params, workspace_id):
    """Execute a CRM data query and return structured results."""
    import logging
    logger = logging.getLogger(__name__)
    from models import db, User
    from sqlalchemy import or_, and_, func, desc
    from datetime import datetime, timedelta

    params = params or {}
    filters = params.get('filters', {})
    query_text = params.get('query', '').strip()
    limit = min(params.get('limit', 20), 50)

    try:
        # ── SEARCH CONTACTS ──
        if query_type == 'search_contacts':
            q = Contact.query.filter_by(workspace_id=workspace_id, is_deleted=False)
            if query_text:
                parts = query_text.split()
                if len(parts) >= 2:
                    q = q.filter(and_(
                        Contact.first_name.ilike(f'%{parts[0]}%'),
                        Contact.last_name.ilike(f'%{parts[1]}%')
                    ))
                else:
                    q = q.filter(or_(
                        Contact.first_name.ilike(f'%{query_text}%'),
                        Contact.last_name.ilike(f'%{query_text}%'),
                        Contact.email.ilike(f'%{query_text}%'),
                        Contact.phone.ilike(f'%{query_text}%')
                    ))
            if filters.get('role'):
                q = q.filter(Contact.role.ilike(f'%{filters["role"]}%'))
            if filters.get('lifecycle_stage'):
                q = q.filter(Contact.lifecycle_stage == filters['lifecycle_stage'])
            if filters.get('company_name'):
                q = q.join(Company, Contact.company_id == Company.id).filter(
                    Company.name.ilike(f'%{filters["company_name"]}%'))
            if filters.get('lead_score_min'):
                q = q.filter(Contact.lead_score >= int(filters['lead_score_min']))

            contacts = q.order_by(Contact.created_at.desc()).limit(limit).all()
            return {
                'type': 'contacts',
                'count': len(contacts),
                'data': [{
                    'id': c.id,
                    'name': c.full_name,
                    'email': c.email or '-',
                    'phone': c.phone or '-',
                    'company': c.company.name if c.company else '-',
                    'role': c.role or '-',
                    'position': c.job_title or '-',
                    'lifecycle': c.lifecycle_stage or '-',
                    'lead_score': c.lead_score or 0,
                    'created': c.created_at.strftime('%d.%m.%Y') if c.created_at else '-'
                } for c in contacts]
            }

        # ── SEARCH COMPANIES ──
        elif query_type == 'search_companies':
            q = Company.query.filter_by(workspace_id=workspace_id, is_deleted=False)
            if query_text:
                q = q.filter(Company.name.ilike(f'%{query_text}%'))
            if filters.get('industry'):
                q = q.filter(Company.industry.ilike(f'%{filters["industry"]}%'))
            if filters.get('size'):
                q = q.filter(Company.size == filters['size'])

            companies = q.order_by(Company.created_at.desc()).limit(limit).all()
            return {
                'type': 'companies',
                'count': len(companies),
                'data': [{
                    'id': c.id,
                    'name': c.name,
                    'industry': c.industry or '-',
                    'size': c.size or '-',
                    'website': c.website or '-',
                    'email': c.email or '-',
                    'phone': c.phone or '-',
                    'contact_count': len([ct for ct in c.contacts if not ct.is_deleted]) if c.contacts else 0,
                    'deal_count': len([d for d in c.deals if not d.is_deleted]) if c.deals else 0,
                    'created': c.created_at.strftime('%d.%m.%Y') if c.created_at else '-'
                } for c in companies]
            }

        # ── SEARCH DEALS ──
        elif query_type == 'search_deals':
            q = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False)
            if query_text:
                q = q.filter(Deal.name.ilike(f'%{query_text}%'))
            if filters.get('status'):
                q = q.filter(Deal.status == filters['status'])
            if filters.get('stage_name'):
                from models_crm import DealStage
                q = q.join(DealStage, Deal.stage_id == DealStage.id).filter(
                    DealStage.name.ilike(f'%{filters["stage_name"]}%'))
            if filters.get('min_value'):
                q = q.filter(Deal.value >= float(filters['min_value']))
            if filters.get('max_value'):
                q = q.filter(Deal.value <= float(filters['max_value']))

            deals = q.order_by(Deal.created_at.desc()).limit(limit).all()
            return {
                'type': 'deals',
                'count': len(deals),
                'data': [{
                    'id': d.id,
                    'name': d.name,
                    'value': f'{float(d.value or 0):,.0f} TL',
                    'status': d.status,
                    'stage': d.stage.name if d.stage else '-',
                    'company': d.company.name if d.company else '-',
                    'contact': d.primary_contact.full_name if d.primary_contact else '-',
                    'expected_close': d.expected_close_date.strftime('%d.%m.%Y') if d.expected_close_date else '-',
                    'days_open': (datetime.utcnow() - d.created_at).days if d.created_at else 0,
                    'created': d.created_at.strftime('%d.%m.%Y') if d.created_at else '-'
                } for d in deals]
            }

        # ── GET CONTACT DETAIL ──
        elif query_type == 'get_contact_detail':
            contact = None
            if params.get('contact_id'):
                contact = Contact.query.filter_by(id=params['contact_id'], workspace_id=workspace_id, is_deleted=False).first()
            elif params.get('name'):
                name = params['name'].strip()
                parts = name.split()
                if len(parts) >= 2:
                    contact = Contact.query.filter(
                        Contact.workspace_id == workspace_id, Contact.is_deleted == False,
                        and_(Contact.first_name.ilike(f'%{parts[0]}%'), Contact.last_name.ilike(f'%{parts[1]}%'))
                    ).first()
                else:
                    contact = Contact.query.filter(
                        Contact.workspace_id == workspace_id, Contact.is_deleted == False,
                        or_(Contact.first_name.ilike(f'%{name}%'), Contact.last_name.ilike(f'%{name}%'))
                    ).first()
            if not contact:
                return {'type': 'error', 'message': 'Contact bulunamadı'}

            # Get deals
            deals = Deal.query.filter_by(contact_id=contact.id, workspace_id=workspace_id, is_deleted=False).all()
            # Get recent activities
            activities = Activity.query.filter_by(contact_id=contact.id, workspace_id=workspace_id).order_by(Activity.created_at.desc()).limit(5).all()
            # Get tasks
            tasks = Task.query.filter_by(contact_id=contact.id, workspace_id=workspace_id).filter(Task.status != 'cancelled').order_by(Task.created_at.desc()).limit(5).all()

            return {
                'type': 'contact_detail',
                'data': {
                    'id': contact.id,
                    'name': contact.full_name,
                    'email': contact.email or '-',
                    'phone': contact.phone or '-',
                    'company': contact.company.name if contact.company else '-',
                    'role': contact.role or '-',
                    'position': contact.job_title or '-',
                    'lifecycle': contact.lifecycle_stage or '-',
                    'lead_score': contact.lead_score or 0,
                    'lead_source': contact.lead_source or '-',
                    'created': contact.created_at.strftime('%d.%m.%Y %H:%M') if contact.created_at else '-',
                    'deals': [{'name': d.name, 'value': f'{float(d.value or 0):,.0f} TL', 'status': d.status} for d in deals],
                    'recent_activities': [{'type': a.activity_type, 'subject': a.subject or '', 'date': a.created_at.strftime('%d.%m.%Y')} for a in activities],
                    'tasks': [{'title': t.title, 'status': t.status, 'due': t.due_date.strftime('%d.%m.%Y') if t.due_date else '-'} for t in tasks],
                    'tags': [t.name for t in contact.tags] if contact.tags else []
                }
            }

        # ── GET COMPANY DETAIL ──
        elif query_type == 'get_company_detail':
            company = None
            if params.get('company_id'):
                company = Company.query.filter_by(id=params['company_id'], workspace_id=workspace_id, is_deleted=False).first()
            elif params.get('name'):
                company = Company.query.filter(
                    Company.workspace_id == workspace_id, Company.is_deleted == False,
                    Company.name.ilike(f'%{params["name"]}%')
                ).first()
            if not company:
                return {'type': 'error', 'message': 'Şirket bulunamadı'}

            contacts = Contact.query.filter_by(company_id=company.id, workspace_id=workspace_id, is_deleted=False).limit(10).all()
            deals = Deal.query.filter_by(company_id=company.id, workspace_id=workspace_id, is_deleted=False).limit(10).all()

            return {
                'type': 'company_detail',
                'data': {
                    'id': company.id,
                    'name': company.name,
                    'industry': company.industry or '-',
                    'size': company.size or '-',
                    'website': company.website or '-',
                    'email': company.email or '-',
                    'phone': company.phone or '-',
                    'address': company.address or '-',
                    'contacts': [{'name': c.full_name, 'role': c.role or '-', 'email': c.email or '-'} for c in contacts],
                    'deals': [{'name': d.name, 'value': f'{float(d.value or 0):,.0f} TL', 'status': d.status} for d in deals],
                    'total_deal_value': f'{sum(float(d.value or 0) for d in deals):,.0f} TL'
                }
            }

        # ── GET DEAL DETAIL ──
        elif query_type == 'get_deal_detail':
            deal = None
            if params.get('deal_id'):
                deal = Deal.query.filter_by(id=params['deal_id'], workspace_id=workspace_id, is_deleted=False).first()
            elif params.get('name'):
                deal = Deal.query.filter(
                    Deal.workspace_id == workspace_id, Deal.is_deleted == False,
                    Deal.name.ilike(f'%{params["name"]}%')
                ).first()
            if not deal:
                return {'type': 'error', 'message': 'Deal bulunamadı'}

            stakeholders = []
            if deal.stakeholder_links:
                for sl in deal.stakeholder_links[:10]:
                    if sl.contact:
                        stakeholders.append({'name': sl.contact.full_name, 'role': sl.role or '-'})

            return {
                'type': 'deal_detail',
                'data': {
                    'id': deal.id,
                    'name': deal.name,
                    'value': f'{float(deal.value or 0):,.0f} TL',
                    'status': deal.status,
                    'stage': deal.stage.name if deal.stage else '-',
                    'company': deal.company.name if deal.company else '-',
                    'contact': deal.primary_contact.full_name if deal.primary_contact else '-',
                    'expected_close': deal.expected_close_date.strftime('%d.%m.%Y') if deal.expected_close_date else '-',
                    'next_step': deal.next_step or '-',
                    'days_open': (datetime.utcnow() - deal.created_at).days if deal.created_at else 0,
                    'ai_score': deal.ai_score,
                    'stakeholders': stakeholders,
                    'created': deal.created_at.strftime('%d.%m.%Y') if deal.created_at else '-'
                }
            }

        # ── LIST TASKS ──
        elif query_type == 'list_tasks':
            q = Task.query.filter_by(workspace_id=workspace_id)
            if params.get('status'):
                q = q.filter(Task.status == params['status'])
            if params.get('priority'):
                q = q.filter(Task.priority == params['priority'])
            if params.get('task_type'):
                q = q.filter(Task.task_type == params['task_type'])
            if params.get('assignee_name'):
                q = q.join(User, Task.assignee_id == User.id).filter(
                    or_(User.name.ilike(f'%{params["assignee_name"]}%'),
                        User.email.ilike(f'%{params["assignee_name"]}%')))
            if params.get('date_from'):
                try:
                    q = q.filter(Task.due_date >= datetime.strptime(params['date_from'], '%Y-%m-%d'))
                except: pass
            if params.get('date_to'):
                try:
                    q = q.filter(Task.due_date <= datetime.strptime(params['date_to'], '%Y-%m-%d'))
                except: pass

            tasks = q.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).limit(limit).all()
            return {
                'type': 'tasks',
                'count': len(tasks),
                'data': [{
                    'id': t.id,
                    'title': t.title,
                    'status': t.status,
                    'priority': t.priority,
                    'type': t.task_type,
                    'due_date': t.due_date.strftime('%d.%m.%Y') if t.due_date else '-',
                    'assignee': '',
                    'deal': t.deal.name if t.deal else '-',
                    'created': t.created_at.strftime('%d.%m.%Y') if t.created_at else '-'
                } for t in tasks]
            }

        # ── LIST ACTIVITIES ──
        elif query_type == 'list_activities':
            q = Activity.query.filter_by(workspace_id=workspace_id, is_deleted=False)
            if params.get('entity_type') == 'contact' and params.get('entity_id'):
                q = q.filter(Activity.contact_id == int(params['entity_id']))
            elif params.get('entity_type') == 'company' and params.get('entity_id'):
                q = q.filter(Activity.company_id == int(params['entity_id']))
            elif params.get('entity_type') == 'deal' and params.get('entity_id'):
                q = q.filter(Activity.deal_id == int(params['entity_id']))
            if params.get('activity_type'):
                q = q.filter(Activity.activity_type == params['activity_type'])

            activities = q.order_by(Activity.created_at.desc()).limit(limit).all()
            return {
                'type': 'activities',
                'count': len(activities),
                'data': [{
                    'id': a.id,
                    'type': a.activity_type,
                    'subject': a.subject or '-',
                    'body': (a.body or '')[:200],
                    'date': a.created_at.strftime('%d.%m.%Y %H:%M') if a.created_at else '-'
                } for a in activities]
            }

        # ── LIST NOTES ──
        elif query_type == 'list_notes':
            from models_crm import Activity as Act
            q = Act.query.filter_by(workspace_id=workspace_id, is_deleted=False, activity_type='note')
            if params.get('entity_type') == 'contact' and params.get('entity_id'):
                q = q.filter(Act.contact_id == int(params['entity_id']))
            elif params.get('entity_type') == 'deal' and params.get('entity_id'):
                q = q.filter(Act.deal_id == int(params['entity_id']))
            if params.get('query'):
                q = q.filter(or_(
                    Act.subject.ilike(f'%{params["query"]}%'),
                    Act.body.ilike(f'%{params["query"]}%')
                ))

            notes = q.order_by(Act.created_at.desc()).limit(limit).all()
            return {
                'type': 'notes',
                'count': len(notes),
                'data': [{
                    'id': n.id,
                    'subject': n.subject or '-',
                    'content': (n.body or '')[:300],
                    'date': n.created_at.strftime('%d.%m.%Y %H:%M') if n.created_at else '-'
                } for n in notes]
            }

        # ── LIST TEAM MEMBERS ──
        elif query_type == 'list_team_members':
            members = User.query.filter_by(workspace_id=workspace_id, is_active=True).all()
            return {
                'type': 'team_members',
                'count': len(members),
                'data': [{
                    'id': u.id,
                    'name': u.name or u.email,
                    'email': u.email,
                    'role': u.role or 'member',
                    'last_login': u.last_login.strftime('%d.%m.%Y') if u.last_login else '-'
                } for u in members]
            }

        # ── CRM STATS ──
        elif query_type == 'crm_stats':
            total_contacts = Contact.query.filter_by(workspace_id=workspace_id, is_deleted=False).count()
            total_companies = Company.query.filter_by(workspace_id=workspace_id, is_deleted=False).count()
            total_deals_open = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False, status='open').count()
            total_deals_won = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False, status='won').count()
            total_deals_lost = Deal.query.filter_by(workspace_id=workspace_id, is_deleted=False, status='lost').count()
            open_value = db.session.query(func.sum(Deal.value)).filter_by(workspace_id=workspace_id, is_deleted=False, status='open').scalar() or 0
            won_value = db.session.query(func.sum(Deal.value)).filter_by(workspace_id=workspace_id, is_deleted=False, status='won').scalar() or 0
            total_tasks = Task.query.filter_by(workspace_id=workspace_id).count()
            pending_tasks = Task.query.filter_by(workspace_id=workspace_id, status='not_started').count()
            overdue_tasks = Task.query.filter(
                Task.workspace_id == workspace_id,
                Task.status.notin_(['completed', 'cancelled']),
                Task.due_date < datetime.utcnow()
            ).count()
            win_rate = f'{(total_deals_won / (total_deals_won + total_deals_lost) * 100):.0f}%' if (total_deals_won + total_deals_lost) > 0 else '0%'

            return {
                'type': 'crm_stats',
                'data': {
                    'contacts': total_contacts,
                    'companies': total_companies,
                    'open_deals': total_deals_open,
                    'won_deals': total_deals_won,
                    'lost_deals': total_deals_lost,
                    'win_rate': win_rate,
                    'open_pipeline_value': f'{float(open_value):,.0f} TL',
                    'won_revenue': f'{float(won_value):,.0f} TL',
                    'total_tasks': total_tasks,
                    'pending_tasks': pending_tasks,
                    'overdue_tasks': overdue_tasks
                }
            }

        # ── PIPELINE SUMMARY ──
        elif query_type == 'pipeline_summary':
            from models_crm import DealStage, Pipeline
            pipeline_id = params.get('pipeline_id')
            if not pipeline_id:
                pipeline = Pipeline.query.filter_by(workspace_id=workspace_id, is_default=True).first()
                if not pipeline:
                    pipeline = Pipeline.query.filter_by(workspace_id=workspace_id).first()
                if pipeline:
                    pipeline_id = pipeline.id

            if not pipeline_id:
                return {'type': 'error', 'message': 'Pipeline bulunamadı'}

            stages = db.session.query(
                DealStage.name, DealStage.order,
                func.count(Deal.id),
                func.sum(Deal.value)
            ).outerjoin(Deal, and_(
                Deal.stage_id == DealStage.id,
                Deal.status == 'open',
                Deal.is_deleted == False
            )).filter(
                DealStage.pipeline_id == pipeline_id,
                DealStage.is_active == True
            ).group_by(DealStage.name, DealStage.order).order_by(DealStage.order).all()

            return {
                'type': 'pipeline_summary',
                'data': [{
                    'stage': s[0],
                    'order': s[1],
                    'deal_count': s[2] or 0,
                    'total_value': f'{float(s[3] or 0):,.0f} TL'
                } for s in stages]
            }

        # ── LIST CUSTOM FIELDS ──
        elif query_type == 'list_custom_fields':
            from models_crm import CustomField
            entity_type = params.get('entity_type', 'contact')
            fields = CustomField.query.filter_by(workspace_id=workspace_id, entity_type=entity_type).all()
            return {
                'type': 'custom_fields',
                'entity_type': entity_type,
                'data': [{
                    'id': f.id,
                    'name': f.field_name,
                    'type': f.field_type,
                    'required': f.is_required,
                    'options': f.options
                } for f in fields]
            }

        # ── SEARCH TAGS ──
        elif query_type == 'search_tags':
            from models_crm import Tag
            q = Tag.query.filter_by(workspace_id=workspace_id)
            if params.get('query'):
                q = q.filter(Tag.name.ilike(f'%{params["query"]}%'))
            tags = q.limit(20).all()
            return {
                'type': 'tags',
                'data': [{'id': t.id, 'name': t.name, 'color': t.color} for t in tags]
            }

        else:
            return {'type': 'error', 'message': f'Bilinmeyen sorgu tipi: {query_type}'}

    except Exception as e:
        logger.error(f'CRM query error ({query_type}): {e}', exc_info=True)
        return {'type': 'error', 'message': str(e)}


def _format_query_result(result):
    """Format CRM query result dict into readable Turkish text."""
    if result.get('type') == 'error':
        return f"❌ {result.get('message', 'Bilinmeyen hata')}"

    rtype = result.get('type', '')
    data = result.get('data', [])

    if rtype == 'crm_stats' and isinstance(data, dict):
        lines = ['📊 CRM İstatistikleri:\n']
        labels = {
            'contacts': '👤 Kişiler', 'companies': '🏢 Şirketler',
            'open_deals': '📂 Açık Deal', 'won_deals': '✅ Kazanılan',
            'lost_deals': '❌ Kaybedilen', 'win_rate': '📈 Kazanma Oranı',
            'open_pipeline_value': '💰 Açık Pipeline', 'won_revenue': '💵 Toplam Gelir',
            'total_tasks': '📋 Toplam Görev', 'pending_tasks': '⏳ Bekleyen',
            'overdue_tasks': '🔴 Geciken'
        }
        for k, v in data.items():
            lines.append(f'  {labels.get(k, k)}: {v}')
        return '\n'.join(lines)

    if rtype == 'pipeline_summary':
        lines = ['📊 Pipeline Özeti:\n']
        for s in data:
            lines.append(f"  {s['stage']}: {s['deal_count']} deal — {s['total_value']}")
        return '\n'.join(lines) if data else 'Pipeline verisi bulunamadı.'

    if rtype in ('contact_detail', 'company_detail', 'deal_detail') and isinstance(data, dict):
        lines = [f"📋 {data.get('name', 'Detay')}:\n"]
        skip_keys = {'id', 'name'}
        for k, v in data.items():
            if k in skip_keys:
                continue
            if isinstance(v, list):
                if v:
                    lines.append(f'\n  {k.upper()}:')
                    for item in v[:5]:
                        if isinstance(item, dict):
                            lines.append('    • ' + ', '.join(f'{ik}: {iv}' for ik, iv in item.items()))
                        else:
                            lines.append(f'    • {item}')
            else:
                lines.append(f'  {k}: {v}')
        return '\n'.join(lines)

    if isinstance(data, list):
        count = result.get('count', len(data))
        if not data:
            return f'Sonuç bulunamadı (0 kayıt).'
        lines = [f'📋 {count} kayıt bulundu:\n']
        for i, item in enumerate(data[:15], 1):
            if isinstance(item, dict):
                name = item.get('name') or item.get('title') or item.get('subject') or f'#{item.get("id", i)}'
                details = []
                for k, v in item.items():
                    if k in ('id', 'name', 'title'):
                        continue
                    if v and v != '-':
                        details.append(f'{k}: {v}')
                detail_str = ' | '.join(details[:4])
                lines.append(f'  {i}. {name} — {detail_str}')
            else:
                lines.append(f'  {i}. {item}')
        if count > 15:
            lines.append(f'\n  ... ve {count - 15} kayıt daha.')
        return '\n'.join(lines)

    return str(result)


def _auto_execute_action(action, params, workspace_id, user_id):
    """Auto-execute non-confirmation actions (add_note, create_task, complete_task)."""
    from models import db
    from datetime import datetime, timedelta
    import logging
    logger = logging.getLogger(__name__)

    params = params or {}
    try:
        # ── ADD NOTE ──
        if action == 'add_note':
            entity_type = params.get('entity_type', 'contact')
            entity_name = params.get('entity_name', '').strip()
            entity_id = params.get('entity_id')
            content = params.get('content', '').strip()
            note_type = params.get('note_type', 'note')

            if not content:
                return '❌ Not içeriği boş olamaz.'

            # Resolve entity
            contact_id = company_id = deal_id = None
            resolved_name = entity_name

            if entity_type == 'contact':
                if not entity_id and entity_name:
                    from sqlalchemy import or_, and_
                    parts = entity_name.split()
                    if len(parts) >= 2:
                        c = Contact.query.filter(Contact.workspace_id == workspace_id, Contact.is_deleted == False,
                            and_(Contact.first_name.ilike(f'%{parts[0]}%'), Contact.last_name.ilike(f'%{parts[1]}%'))).first()
                    else:
                        c = Contact.query.filter(Contact.workspace_id == workspace_id, Contact.is_deleted == False,
                            or_(Contact.first_name.ilike(f'%{entity_name}%'), Contact.last_name.ilike(f'%{entity_name}%'))).first()
                    if c:
                        contact_id = c.id
                        resolved_name = c.full_name
                    else:
                        return f'❌ "{entity_name}" adlı contact bulunamadı.'
                else:
                    contact_id = entity_id
            elif entity_type == 'company':
                if not entity_id and entity_name:
                    comp = Company.query.filter(Company.workspace_id == workspace_id, Company.is_deleted == False,
                        Company.name.ilike(f'%{entity_name}%')).first()
                    if comp:
                        company_id = comp.id
                        resolved_name = comp.name
                    else:
                        return f'❌ "{entity_name}" adlı şirket bulunamadı.'
                else:
                    company_id = entity_id
            elif entity_type == 'deal':
                if not entity_id and entity_name:
                    d = Deal.query.filter(Deal.workspace_id == workspace_id, Deal.is_deleted == False,
                        Deal.name.ilike(f'%{entity_name}%')).first()
                    if d:
                        deal_id = d.id
                        resolved_name = d.name
                    else:
                        return f'❌ "{entity_name}" adlı deal bulunamadı.'
                else:
                    deal_id = entity_id

            activity = Activity(
                workspace_id=workspace_id,
                activity_type=note_type,
                contact_id=contact_id,
                company_id=company_id,
                deal_id=deal_id,
                user_id=user_id,
                subject=f'Not — {resolved_name}',
                body=content,
                created_at=datetime.utcnow()
            )
            db.session.add(activity)
            db.session.commit()
            return f'✅ "{resolved_name}" kaydına not eklendi: "{content[:80]}..."'

        # ── CREATE TASK ──
        elif action == 'create_task':
            title = params.get('title', '').strip()
            if not title:
                return '❌ Görev başlığı boş olamaz.'

            description = params.get('description', '')
            priority = params.get('priority', 'medium')
            task_type = params.get('task_type', 'todo')
            due_date_str = params.get('due_date', '')

            # Parse due date
            due_date = None
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
                except:
                    due_date = datetime.utcnow() + timedelta(days=7)
            else:
                due_date = datetime.utcnow() + timedelta(days=7)

            # Resolve assignee
            assignee_id = user_id
            if params.get('assignee_name'):
                from models import User
                from sqlalchemy import or_
                u = User.query.filter(or_(
                    User.name.ilike(f'%{params["assignee_name"]}%'),
                    User.email.ilike(f'%{params["assignee_name"]}%')
                )).first()
                if u:
                    assignee_id = u.id

            # Resolve contact
            contact_id = None
            if params.get('contact_name'):
                from sqlalchemy import or_
                cn = params['contact_name'].strip()
                parts = cn.split()
                if len(parts) >= 2:
                    c = Contact.query.filter(Contact.workspace_id == workspace_id, Contact.is_deleted == False,
                        Contact.first_name.ilike(f'%{parts[0]}%'), Contact.last_name.ilike(f'%{parts[1]}%')).first()
                else:
                    c = Contact.query.filter(Contact.workspace_id == workspace_id, Contact.is_deleted == False,
                        or_(Contact.first_name.ilike(f'%{cn}%'), Contact.last_name.ilike(f'%{cn}%'))).first()
                if c:
                    contact_id = c.id

            # Resolve deal
            deal_id = None
            if params.get('deal_name'):
                d = Deal.query.filter(Deal.workspace_id == workspace_id, Deal.is_deleted == False,
                    Deal.name.ilike(f'%{params["deal_name"]}%')).first()
                if d:
                    deal_id = d.id

            # Resolve company
            company_id = None
            if params.get('company_name'):
                comp = Company.query.filter(Company.workspace_id == workspace_id, Company.is_deleted == False,
                    Company.name.ilike(f'%{params["company_name"]}%')).first()
                if comp:
                    company_id = comp.id

            start_time = due_date.replace(hour=9, minute=0, second=0) if due_date else None
            end_time = due_date.replace(hour=10, minute=0, second=0) if due_date else None

            task = Task(
                workspace_id=workspace_id,
                title=title,
                description=description or f'AI tarafından oluşturuldu',
                assignee_id=assignee_id,
                deal_id=deal_id,
                contact_id=contact_id,
                company_id=company_id,
                due_date=due_date,
                start_time=start_time,
                end_time=end_time,
                status='not_started',
                priority=priority,
                task_type=task_type,
                reminder_enabled=True,
                reminder_minutes_before=60,
                reminder_method='whatsapp'
            )
            db.session.add(task)
            db.session.commit()
            due_str = due_date.strftime('%d.%m.%Y') if due_date else '-'
            return f'✅ Görev oluşturuldu: "{title}" — Son tarih: {due_str}, Öncelik: {priority}'

        # ── COMPLETE TASK ──
        elif action == 'complete_task':
            task = None
            if params.get('task_id'):
                task = Task.query.filter_by(id=params['task_id'], workspace_id=workspace_id).first()
            elif params.get('title'):
                task = Task.query.filter(
                    Task.workspace_id == workspace_id,
                    Task.title.ilike(f'%{params["title"]}%'),
                    Task.status != 'completed'
                ).first()
            if not task:
                return '❌ Görev bulunamadı.'
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
            db.session.commit()
            return f'✅ "{task.title}" görevi tamamlandı.'

        return '❌ Bilinmeyen aksiyon.'
    except Exception as e:
        db.session.rollback()
        logger.error(f'Auto execute error ({action}): {e}', exc_info=True)
        return f'❌ Hata: {str(e)}'


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
        # Priority: Groq > OpenRouter > MiniMax > Gemini > Anthropic
        if ai['groq_key']:
            provider = 'groq'
        elif ai['openrouter_key']:
            provider = 'openrouter'
        elif ai['minimax_key']:
            provider = 'minimax'
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
            
        elif provider == 'minimax' and ai['minimax_key']:
            # MiniMax Anthropic-compatible API
            try:
                headers = {
                    'Authorization': f"Bearer {ai['minimax_key']}",
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                }
                minimax_messages = [{'role': 'system', 'content': system_prompt}] + messages if system_prompt else messages
                payload = {
                    'model': ai['minimax_model'],
                    'max_tokens': 1024,
                    'messages': [{'role': m['role'], 'content': m['content']} for m in minimax_messages]
                }
                logger.info(f"[MiniMax] Sending request to MiniMax API, model={ai['minimax_model']}, key_len={len(ai['minimax_key'])}")
                logger.info(f"[MiniMax] Payload messages: {len(payload['messages'])}")
                response = requests.post(
                    'https://api.minimax.io/anthropic/v1/messages',
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                logger.info(f"[MiniMax] Status: {response.status_code}")
                logger.info(f"[MiniMax] Response body: {response.text[:1000]}")
                response.raise_for_status()
                data = response.json()
                logger.info(f"[MiniMax] Response data keys: {list(data.keys())}")
                logger.info(f"[MiniMax] Content type: {type(data.get('content'))}")
                logger.info(f"[MiniMax] Content: {data.get('content')}")
                # MiniMax returns Anthropic-compatible format with content blocks
                if data.get('content') and len(data['content']) > 0:
                    content_block = data['content'][0]
                    logger.info(f"[MiniMax] Content block: {content_block}")
                    if content_block.get('type') == 'text':
                        response_text = content_block.get('text', '')
                        logger.info(f"[MiniMax] Extracted text: {response_text[:100] if response_text else 'EMPTY'}")
                        return jsonify({'response': response_text})
                    elif content_block.get('text'):
                        return jsonify({'response': content_block.get('text')})
                logger.warning(f"[MiniMax] No valid content in response, returning empty")
                return jsonify({'response': ''})
            except Exception as minimax_error:
                logger.error(f"[MiniMax] Error: {str(minimax_error)}")
                import traceback
                logger.error(f"[MiniMax] Traceback: {traceback.format_exc()}")
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
        # Priority: Groq > OpenRouter > MiniMax > Gemini > Anthropic
        if ai.get('groq_client'):
            groq_messages = [{'role': 'system', 'content': system}] + messages
            response = ai['groq_client'].chat.completions.create(
                model=ai['groq_model'],
                messages=groq_messages,
                max_tokens=1024,
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
                'max_tokens': 1024,
            }
            response = requests.post('https://openrouter.ai/api/v1/chat/completions',
                                    headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']

        elif ai.get('minimax_key'):
            headers = {
                'Authorization': f"Bearer {ai['minimax_key']}",
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }
            minimax_messages = [{'role': 'system', 'content': system}] + messages
            payload = {
                'model': ai['minimax_model'],
                'max_tokens': 2048,
                'messages': [{'role': m['role'], 'content': m['content']} for m in minimax_messages]
            }
            response = requests.post(
                'https://api.minimax.io/anthropic/v1/messages',
                headers=headers,
                json=payload,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            if data.get('content') and isinstance(data['content'], list):
                thinking_fallback = ''
                # Iterate to find the text block (skipping thinking blocks)
                for block in data['content']:
                    if isinstance(block, dict):
                        if block.get('type') == 'text' and block.get('text'):
                            return block.get('text')
                        elif block.get('type') == 'thinking' and block.get('thinking'):
                            thinking_fallback = block.get('thinking')
                
                # If cut off max_tokens and only thinking exists
                if thinking_fallback:
                    return "*(Model yanıtı bitiremedi)*\n\nDüşünme süreci:\n" + thinking_fallback
            return str(data)

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
                max_tokens=1024,
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
            if params.get('lead_source'):
                contact.lead_source = params['lead_source']
                updated_fields.append(f"kaynak: {params['lead_source']}")
            if params.get('lifecycle_stage'):
                contact.lifecycle_stage = params['lifecycle_stage']
                updated_fields.append(f"yaşam döngüsü: {params['lifecycle_stage']}")

            if not updated_fields:
                return jsonify({'error': 'Güncellenecek alan belirtilmedi'}), 400

            db.session.commit()
            return jsonify({
                'message': f'"{contact.full_name}" güncellendi: {", ".join(updated_fields)}',
                'id': contact.id
            })

        elif action == 'update_deal_value':
            deal_id = params.get('deal_id')
            deal_name = params.get('deal_name', '').strip()
            value = params.get('value')
            if not deal_id and deal_name:
                deal = Deal.query.filter(Deal.workspace_id == workspace_id, Deal.is_deleted == False,
                    Deal.name.ilike(f'%{deal_name}%')).first()
                if not deal:
                    return jsonify({'error': f'"{deal_name}" adlı deal bulunamadı'}), 404
            else:
                deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id).first_or_404()
            deal.value = float(value)
            db.session.commit()
            return jsonify({'message': f'"{deal.name}" deal değeri {float(value):,.0f} TL olarak güncellendi.'})

        # ── CREATE COMPANY ──
        elif action == 'create_company':
            name = params.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Şirket adı zorunlu'}), 400
            company = Company(
                workspace_id=workspace_id,
                name=name,
                industry=params.get('industry', ''),
                size=params.get('size', ''),
                website=params.get('website', ''),
                email=params.get('email', ''),
                phone=params.get('phone', ''),
                address=params.get('address', '')
            )
            db.session.add(company)
            db.session.commit()
            return jsonify({'message': f'"{name}" şirketi oluşturuldu.', 'id': company.id})

        # ── UPDATE COMPANY ──
        elif action == 'update_company':
            company = None
            company_id = params.get('company_id')
            company_name = params.get('name', '').strip()
            if company_id:
                company = Company.query.filter_by(id=company_id, workspace_id=workspace_id, is_deleted=False).first()
            elif company_name:
                company = Company.query.filter(
                    Company.workspace_id == workspace_id, Company.is_deleted == False,
                    Company.name.ilike(f'%{company_name}%')
                ).first()
            if not company:
                return jsonify({'error': 'Şirket bulunamadı'}), 404

            updated = []
            for field, attr in [('industry', 'industry'), ('size', 'size'), ('website', 'website'),
                                ('email', 'email'), ('phone', 'phone'), ('address', 'address')]:
                if params.get(field):
                    setattr(company, attr, params[field])
                    updated.append(f'{field}: {params[field]}')
            if params.get('new_name'):
                company.name = params['new_name']
                updated.append(f'isim: {params["new_name"]}')

            if not updated:
                return jsonify({'error': 'Güncellenecek alan belirtilmedi'}), 400
            db.session.commit()
            return jsonify({'message': f'"{company.name}" güncellendi: {", ".join(updated)}', 'id': company.id})

        # ── UPDATE DEAL STAGE ──
        elif action == 'update_deal_stage':
            from models_crm import DealStage
            deal = None
            deal_id = params.get('deal_id')
            deal_name = params.get('deal_name', '').strip()
            stage_name = params.get('stage_name', '').strip()

            if not stage_name:
                return jsonify({'error': 'Aşama adı gerekli'}), 400

            if deal_id:
                deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id, is_deleted=False).first()
            elif deal_name:
                deal = Deal.query.filter(Deal.workspace_id == workspace_id, Deal.is_deleted == False,
                    Deal.name.ilike(f'%{deal_name}%')).first()
            if not deal:
                return jsonify({'error': 'Deal bulunamadı'}), 404

            stage = DealStage.query.filter(
                DealStage.pipeline_id == deal.pipeline_id,
                DealStage.name.ilike(f'%{stage_name}%'),
                DealStage.is_active == True
            ).first()
            if not stage:
                return jsonify({'error': f'"{stage_name}" aşaması bulunamadı'}), 404

            from datetime import datetime
            deal.stage_id = stage.id
            deal.stage_entered_at = datetime.utcnow()
            deal.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'message': f'"{deal.name}" aşaması "{stage.name}" olarak güncellendi.'})

        # ── DELETE RECORD (soft delete) ──
        elif action == 'delete_record':
            entity_type = params.get('entity_type', '').strip()
            entity_id = params.get('entity_id')
            entity_name = params.get('name', '').strip()
            from datetime import datetime

            if entity_type == 'contact':
                obj = None
                if entity_id:
                    obj = Contact.query.filter_by(id=entity_id, workspace_id=workspace_id, is_deleted=False).first()
                elif entity_name:
                    parts = entity_name.split()
                    if len(parts) >= 2:
                        obj = Contact.query.filter(Contact.workspace_id == workspace_id, Contact.is_deleted == False,
                            Contact.first_name.ilike(f'%{parts[0]}%'), Contact.last_name.ilike(f'%{parts[1]}%')).first()
                    else:
                        obj = Contact.query.filter(Contact.workspace_id == workspace_id, Contact.is_deleted == False,
                            or_(Contact.first_name.ilike(f'%{entity_name}%'), Contact.last_name.ilike(f'%{entity_name}%'))).first()
                if not obj:
                    return jsonify({'error': 'Contact bulunamadı'}), 404
                obj.is_deleted = True
                obj.deleted_at = datetime.utcnow()
                db.session.commit()
                return jsonify({'message': f'"{obj.full_name}" silindi.'})

            elif entity_type == 'company':
                obj = None
                if entity_id:
                    obj = Company.query.filter_by(id=entity_id, workspace_id=workspace_id, is_deleted=False).first()
                elif entity_name:
                    obj = Company.query.filter(Company.workspace_id == workspace_id, Company.is_deleted == False,
                        Company.name.ilike(f'%{entity_name}%')).first()
                if not obj:
                    return jsonify({'error': 'Şirket bulunamadı'}), 404
                obj.is_deleted = True
                obj.deleted_at = datetime.utcnow()
                db.session.commit()
                return jsonify({'message': f'"{obj.name}" şirketi silindi.'})

            elif entity_type == 'deal':
                obj = None
                if entity_id:
                    obj = Deal.query.filter_by(id=entity_id, workspace_id=workspace_id, is_deleted=False).first()
                elif entity_name:
                    obj = Deal.query.filter(Deal.workspace_id == workspace_id, Deal.is_deleted == False,
                        Deal.name.ilike(f'%{entity_name}%')).first()
                if not obj:
                    return jsonify({'error': 'Deal bulunamadı'}), 404
                obj.is_deleted = True
                obj.deleted_at = datetime.utcnow()
                db.session.commit()
                return jsonify({'message': f'"{obj.name}" deal\'i silindi.'})

            return jsonify({'error': f'Bilinmeyen entity tipi: {entity_type}'}), 400

        # ── UPDATE TASK ──
        elif action == 'update_task':
            task = None
            if params.get('task_id'):
                task = Task.query.filter_by(id=params['task_id'], workspace_id=workspace_id).first()
            elif params.get('title'):
                task = Task.query.filter(Task.workspace_id == workspace_id,
                    Task.title.ilike(f'%{params["title"]}%')).first()
            if not task:
                return jsonify({'error': 'Görev bulunamadı'}), 404

            updated = []
            if params.get('status'):
                task.status = params['status']
                updated.append(f'durum: {params["status"]}')
                if params['status'] == 'completed':
                    from datetime import datetime
                    task.completed_at = datetime.utcnow()
            if params.get('priority'):
                task.priority = params['priority']
                updated.append(f'öncelik: {params["priority"]}')
            if params.get('assignee_name'):
                from models import User
                u = User.query.filter(or_(
                    User.name.ilike(f'%{params["assignee_name"]}%'),
                    User.email.ilike(f'%{params["assignee_name"]}%')
                )).first()
                if u:
                    task.assignee_id = u.id
                    updated.append(f'atanan: {u.name or u.email}')

            if not updated:
                return jsonify({'error': 'Güncellenecek alan yok'}), 400
            db.session.commit()
            return jsonify({'message': f'"{task.title}" güncellendi: {", ".join(updated)}'})

        # ── CREATE MEETING ──
        elif action == 'create_meeting':
            from datetime import datetime
            title = params.get('title', '').strip()
            if not title:
                return jsonify({'error': 'Toplantı başlığı zorunlu'}), 400

            start_str = params.get('start_time', '')
            end_str = params.get('end_time', '')
            start_time = None
            end_time = None
            try:
                if start_str:
                    start_time = datetime.strptime(start_str, '%Y-%m-%d %H:%M')
                if end_str:
                    end_time = datetime.strptime(end_str, '%Y-%m-%d %H:%M')
            except:
                pass

            if not start_time:
                start_time = datetime.utcnow().replace(hour=10, minute=0, second=0)
            if not end_time:
                from datetime import timedelta
                end_time = start_time + timedelta(hours=1)

            contact_id = None
            if params.get('contact_name'):
                cn = params['contact_name'].strip()
                parts = cn.split()
                if len(parts) >= 2:
                    c = Contact.query.filter(Contact.workspace_id == workspace_id, Contact.is_deleted == False,
                        Contact.first_name.ilike(f'%{parts[0]}%'), Contact.last_name.ilike(f'%{parts[1]}%')).first()
                else:
                    c = Contact.query.filter(Contact.workspace_id == workspace_id, Contact.is_deleted == False,
                        or_(Contact.first_name.ilike(f'%{cn}%'), Contact.last_name.ilike(f'%{cn}%'))).first()
                if c:
                    contact_id = c.id

            deal_id = None
            if params.get('deal_name'):
                d = Deal.query.filter(Deal.workspace_id == workspace_id, Deal.is_deleted == False,
                    Deal.name.ilike(f'%{params["deal_name"]}%')).first()
                if d:
                    deal_id = d.id

            user_id = session.get('user_id')
            meeting = Task(
                workspace_id=workspace_id,
                title=title,
                description=params.get('description', '') or f'AI tarafından oluşturulan toplantı',
                assignee_id=user_id,
                contact_id=contact_id,
                deal_id=deal_id,
                start_time=start_time,
                end_time=end_time,
                due_date=start_time,
                status='not_started',
                priority='medium',
                task_type='meeting',
                reminder_enabled=True,
                reminder_minutes_before=15,
                reminder_method='whatsapp'
            )
            db.session.add(meeting)
            db.session.commit()
            return jsonify({'message': f'Toplantı oluşturuldu: "{title}" — {start_time.strftime("%d.%m.%Y %H:%M")}'})

        # ── DRAFT EMAIL ──
        elif action == 'draft_email':
            to_name = params.get('to_name', '')
            to_email = params.get('to_email', '')
            subject = params.get('subject', '')
            body = params.get('body', '')
            draft_text = f'📧 E-posta Taslağı\n\nKime: {to_name} <{to_email}>\nKonu: {subject}\n\n{body}'
            return jsonify({'message': draft_text})

        # ── ADD NOTE (via confirmation) ──
        elif action == 'add_note':
            from datetime import datetime
            result = _auto_execute_action('add_note', params, workspace_id, session.get('user_id'))
            return jsonify({'message': result})

        # ── CREATE TASK (via confirmation) ──
        elif action == 'create_task':
            result = _auto_execute_action('create_task', params, workspace_id, session.get('user_id'))
            return jsonify({'message': result})

        # ── COMPLETE TASK (via confirmation) ──
        elif action == 'complete_task':
            result = _auto_execute_action('complete_task', params, workspace_id, session.get('user_id'))
            return jsonify({'message': result})

        # ── UPDATE NOTE ──
        elif action == 'update_note':
            note_id = params.get('note_id')
            content = params.get('content', '').strip()
            mode = params.get('mode', 'replace')
            if not note_id:
                return jsonify({'error': 'note_id gerekli'}), 400
            note = Activity.query.filter_by(id=note_id, workspace_id=workspace_id).first()
            if not note:
                return jsonify({'error': 'Not bulunamadı'}), 404
            if mode == 'append':
                note.body = (note.body or '') + '\n' + content
            elif mode == 'prepend':
                note.body = content + '\n' + (note.body or '')
            else:
                note.body = content
            db.session.commit()
            return jsonify({'message': f'Not güncellendi (mod: {mode})'})

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
