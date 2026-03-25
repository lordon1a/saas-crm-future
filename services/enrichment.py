"""
Auto-Enrichment Engine
Mesajlardan contact bilgisi çıkarır ve DB'yi günceller.
"""
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Regex Parser ────────────────────────────────────────────

PHONE_PATTERNS = [
    r'(\+90[\s\-]?5\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})',  # TR mobil
    r'(0?5\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})',             # TR kısa
    r'(\+\d{1,3}[\s\-]?\d{6,14})',                                   # Uluslararası
]

EMAIL_PATTERN = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'

COMPANY_KEYWORDS = [
    # "X A.Ş", "X Ltd", "X Corp" gibi açık şirket isimleri
    r'([A-ZÇĞİÖŞÜ][a-zA-ZçğışöüñÇĞİÖŞÜ\s&\.]{2,30})\s+(?:A\.Ş|A\.S|Ltd|Corp|Inc|GmbH|LLC)',
    # "şirket: X" veya "firma: X" gibi açık etiketler
    r'(?:şirket|firma|company)\s*:\s*([A-ZÇĞİÖŞÜa-zçğışöüñ\s&\.]{3,40})',
]


def extract_with_regex(text: str) -> dict:
    """Regex ile hızlı veri çıkar."""
    extracted = {}
    
    # Telefon
    for pattern in PHONE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            phone = re.sub(r'[\s\-]', '', match.group(1))
            extracted['phone'] = {'value': phone, 'confidence': 0.95}
            break
    
    # E-posta
    email_match = re.search(EMAIL_PATTERN, text)
    if email_match:
        extracted['email'] = {'value': email_match.group(), 'confidence': 0.99}
    
    # Şirket (regex)
    for pattern in COMPANY_KEYWORDS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            extracted['company_name'] = {'value': match.group(1).strip(), 'confidence': 0.82}
            break
    
    return extracted


def extract_with_llm(text: str, workspace_id: int) -> dict:
    """LLM ile daha zor alanları çıkar (şirket adı vb.)."""
    try:
        from services.enrichment_llm import parse_with_llm
        return parse_with_llm(text, workspace_id)
    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}")
        return {}


def enrich_contact(contact_id: int, workspace_id: int, message_text: str, source: str):
    """
    Ana enrichment fonksiyonu.
    Mesajdan veri çıkar, contact'ı güncelle, log tut.
    """
    from app import db
    from models_crm import Contact, Company, EnrichmentLog
    
    if not message_text or len(message_text.strip()) < 5:
        return
    
    contact = Contact.query.filter_by(
        id=contact_id,
        workspace_id=workspace_id
    ).first()
    
    if not contact:
        return
    
    # Regex ile çıkar
    extracted = extract_with_regex(message_text)
    
    # Regex şirket bulamazsa LLM'e gönder
    if 'company_name' not in extracted and len(message_text) > 20:
        llm_data = extract_with_llm(message_text, workspace_id)
        extracted.update(llm_data)
    
    if not extracted:
        return
    
    updated_fields = []
    
    try:
        for field, data in extracted.items():
            new_value = data['value']
            confidence = data['confidence']
            
            if confidence < 0.7:
                logger.info(f"[Enrichment] Skipping {field} — low confidence {confidence}")
                continue
            
            old_value = None
            
            if field == 'phone':
                old_value = contact.phone
                if not old_value or old_value != new_value:
                    contact.phone = new_value
                else:
                    continue
            
            elif field == 'email':
                old_value = contact.email
                if not old_value or old_value != new_value:
                    contact.email = new_value
                else:
                    continue
            
            elif field == 'company_name':
                old_value = contact.company.name if contact.company else None
                if old_value == new_value:
                    continue
                    
                # Şirketi bul veya oluştur
                company = Company.query.filter_by(
                    name=new_value,
                    workspace_id=workspace_id
                ).first()
                if not company:
                    company = Company(name=new_value, workspace_id=workspace_id)
                    db.session.add(company)
                    db.session.flush()
                contact.company_id = company.id
            
            else:
                continue
            
            # Log kaydet
            log = EnrichmentLog(
                workspace_id=workspace_id,
                contact_id=contact_id,
                source=source,
                field_name=field,
                old_value=str(old_value) if old_value else None,
                new_value=new_value,
                confidence=confidence,
                raw_message=message_text[:500]
            )
            db.session.add(log)
            updated_fields.append(field)
        
        if updated_fields:
            db.session.commit()
            logger.info(f"[Enrichment] Contact {contact_id} updated: {updated_fields} from {source}")
        
        return updated_fields
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Enrichment] Error updating contact {contact_id}: {e}")
        return None
