"""LLM tabanlı entity extraction."""
import json
import logging

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Aşağıdaki mesajdan iletişim bilgilerini çıkar. Sadece açıkça belirtilen bilgileri döndür, tahmin etme.

Mesaj: {text}

Sadece bu JSON formatında yanıt ver, başka hiçbir şey yazma:
{{
  "phone": "telefon numarası veya null",
  "email": "email adresi veya null", 
  "company_name": "şirket adı veya null"
}}"""


def parse_with_llm(text: str, workspace_id: int) -> dict:
    """AI ile entity extraction."""
    from routes.ai_assistant import _get_workspace_ai, _call_ai_raw
    
    ai_config = _get_workspace_ai(workspace_id)
    if not ai_config:
        return {}
    
    prompt = EXTRACTION_PROMPT.format(text=text[:500])
    
    try:
        response_text = _call_ai_raw(
            messages=[{'role': 'user', 'content': prompt}],
            system="Sen bir veri çıkarma asistanısın. Sadece JSON döndür.",
            workspace_id=workspace_id
        )
        
        # JSON parse
        clean = response_text.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        
        data = json.loads(clean)
        result = {}
        
        if data.get('phone') and data['phone'] != 'null':
            result['phone'] = {'value': data['phone'], 'confidence': 0.82}
        if data.get('email') and data['email'] != 'null':
            result['email'] = {'value': data['email'], 'confidence': 0.90}
        if data.get('company_name') and data['company_name'] != 'null':
            result['company_name'] = {'value': data['company_name'], 'confidence': 0.80}
        
        return result
    
    except Exception as e:
        logger.warning(f"[LLM Extraction] Parse error: {e}")
        return {}
