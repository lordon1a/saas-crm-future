"""
AI Scoring Service
Otomatik deal scoring, contact lead scoring, conversation summarization ve sentiment analysis.
AI API'yi kullanarak proaktif insight'lar üretir.
"""
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AIScoringService:
    """AI-powered scoring and insights for deals, contacts, and conversations."""

    @staticmethod
    def score_deal(deal, ai_client, model_name, provider='gemini'):
        """Score a single deal (0-100) and generate insight."""
        from models_crm import DealStage
        from models import db
        from sqlalchemy import func

        stage_name = deal.stage.name if deal.stage else 'Bilinmiyor'
        stage_prob = deal.stage.probability if deal.stage else 50
        days_open = (datetime.utcnow() - deal.created_at).days if deal.created_at else 0
        days_in_stage = (datetime.utcnow() - deal.stage_entered_at).days if deal.stage_entered_at else 0
        days_inactive = 0
        if deal.last_activity_at:
            days_inactive = (datetime.utcnow() - deal.last_activity_at).days
        rotting = deal.stage.rotting_days if deal.stage and deal.stage.rotting_days else 14

        prompt = f"""Asagidaki CRM deal verisini analiz et ve JSON formatinda yanit ver.

Deal: {deal.name}
Deger: {deal.value or 0} TL
Asama: {stage_name} (olaslik: %{stage_prob})
Durum: {deal.status}
Sirket: {deal.company.name if deal.company else 'Yok'}
Ilgili kisi: {deal.primary_contact.full_name if deal.primary_contact else 'Yok'}
Beklenen kapanis: {deal.expected_close_date.strftime('%d.%m.%Y') if deal.expected_close_date else 'Belirsiz'}
Sonraki adim: {deal.next_step or 'Tanimlanmamis'}
Acik gun sayisi: {days_open}
Asamada gun sayisi: {days_in_stage}
Hareketsiz gun: {days_inactive}
Curumeye kadar gun: {rotting}

SADECE su JSON formatinda yanit ver, baska hicbir sey yazma:
{{"score": 0-100, "label": "hot/warm/cold", "insight": "1 cumlelik Turkce ozet ve oneri"}}"""

        try:
            result = _call_ai_simple(prompt, ai_client, model_name, provider)
            parsed = _parse_json(result)
            if parsed:
                deal.ai_score = max(0, min(100, int(parsed.get('score', 50))))
                deal.ai_score_label = parsed.get('label', 'warm')
                deal.ai_insight = parsed.get('insight', '')[:500]
                deal.ai_scored_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Scored deal {deal.id}: {deal.ai_score} ({deal.ai_score_label})")
                return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to score deal {deal.id}: {e}")
        return False

    @staticmethod
    def score_contact(contact, ai_client, model_name, provider='gemini'):
        """Score a contact's lead potential and generate insight."""
        from models_crm import Deal
        from models import db

        deals = Deal.query.filter_by(
            contact_id=contact.id,
            workspace_id=contact.workspace_id,
            is_deleted=False
        ).all()

        total_value = sum(float(d.value or 0) for d in deals)
        won = len([d for d in deals if d.status == 'won'])
        lost = len([d for d in deals if d.status == 'lost'])
        open_deals = len([d for d in deals if d.status == 'open'])
        days_since_created = (datetime.utcnow() - contact.created_at).days if contact.created_at else 0

        prompt = f"""Asagidaki CRM contact verisini analiz et ve JSON formatinda yanit ver.

Kisi: {contact.full_name}
Sirket: {contact.company.name if contact.company else 'Yok'}
Pozisyon: {contact.job_title or 'Belirtilmemis'}
Rol: {contact.role or 'Belirtilmemis'}
Lead kaynagi: {contact.lead_source or 'Belirtilmemis'}
Yasam dongusu: {contact.lifecycle_stage or 'lead'}
Toplam deal: {len(deals)} (kazanilan: {won}, kaybedilen: {lost}, acik: {open_deals})
Toplam deger: {total_value:,.0f} TL
Kayit tarihi: {days_since_created} gun once
Mevcut skor: {contact.lead_score or 0}

SADECE su JSON formatinda yanit ver, baska hicbir sey yazma:
{{"score": 0-100, "insight": "1 cumlelik Turkce lead degerlendirmesi ve oneri"}}"""

        try:
            result = _call_ai_simple(prompt, ai_client, model_name, provider)
            parsed = _parse_json(result)
            if parsed:
                contact.lead_score = max(0, min(100, int(parsed.get('score', 0))))
                contact.ai_insight = parsed.get('insight', '')[:500]
                contact.ai_scored_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Scored contact {contact.id}: {contact.lead_score}")
                return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to score contact {contact.id}: {e}")
        return False

    @staticmethod
    def summarize_conversation(conversation, ai_client, model_name, provider='gemini'):
        """Summarize a WhatsApp conversation and detect sentiment."""
        from models import db, Message

        messages = Message.query.filter_by(
            conversation_id=conversation.id
        ).order_by(Message.created_at.desc()).limit(30).all()

        if not messages:
            return False

        messages_text = '\n'.join([
            f"{'Musteri' if m.sender_type == 'customer' else 'Temsilci'}: {m.message_body[:200]}"
            for m in reversed(messages)
        ])

        prompt = f"""Asagidaki WhatsApp konusmasini analiz et ve JSON formatinda yanit ver.

Konusma:
{messages_text}

SADECE su JSON formatinda yanit ver, baska hicbir sey yazma:
{{"summary": "2-3 cumlelik Turkce ozet", "sentiment": "positive/negative/neutral", "sentiment_score": -1.0 ile 1.0 arasi sayi, "next_action": "onerilen sonraki aksiyon"}}"""

        try:
            result = _call_ai_simple(prompt, ai_client, model_name, provider)
            parsed = _parse_json(result)
            if parsed:
                conversation.ai_summary = parsed.get('summary', '')[:1000]
                conversation.ai_summary_at = datetime.utcnow()
                conversation.ai_sentiment = parsed.get('sentiment', 'neutral')
                conversation.ai_sentiment_score = float(parsed.get('sentiment_score', 0))
                db.session.commit()
                logger.info(f"Summarized conversation {conversation.id}: {conversation.ai_sentiment}")
                return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to summarize conversation {conversation.id}: {e}")
        return False

    @staticmethod
    def get_daily_insights(workspace_id):
        """Generate proactive daily insights for a workspace."""
        from models_crm import Deal, Contact
        from models import db, Conversation
        from sqlalchemy import func

        insights = {
            'stale_deals': [],
            'hot_deals': [],
            'cold_deals': [],
            'high_value_contacts': [],
            'negative_conversations': [],
            'summary': {}
        }

        # Stale deals (no activity > 7 days, still open)
        stale_cutoff = datetime.utcnow() - timedelta(days=7)
        stale_deals = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.status == 'open',
            Deal.is_deleted == False,
            db.or_(
                Deal.last_activity_at < stale_cutoff,
                Deal.last_activity_at.is_(None)
            )
        ).order_by(Deal.value.desc()).limit(10).all()

        for d in stale_deals:
            days = (datetime.utcnow() - d.last_activity_at).days if d.last_activity_at else 999
            insights['stale_deals'].append({
                'id': d.id,
                'name': d.name,
                'value': float(d.value or 0),
                'stage': d.stage.name if d.stage else '',
                'days_inactive': days,
                'company': d.company.name if d.company else ''
            })

        # Hot deals (ai_score > 70)
        hot_deals = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.status == 'open',
            Deal.is_deleted == False,
            Deal.ai_score >= 70
        ).order_by(Deal.ai_score.desc()).limit(5).all()

        for d in hot_deals:
            insights['hot_deals'].append({
                'id': d.id,
                'name': d.name,
                'value': float(d.value or 0),
                'score': d.ai_score,
                'insight': d.ai_insight or '',
                'company': d.company.name if d.company else ''
            })

        # Cold deals (ai_score < 30)
        cold_deals = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.status == 'open',
            Deal.is_deleted == False,
            Deal.ai_score.isnot(None),
            Deal.ai_score < 30
        ).order_by(Deal.ai_score.asc()).limit(5).all()

        for d in cold_deals:
            insights['cold_deals'].append({
                'id': d.id,
                'name': d.name,
                'value': float(d.value or 0),
                'score': d.ai_score,
                'insight': d.ai_insight or '',
                'company': d.company.name if d.company else ''
            })

        # High-value contacts (lead_score > 70)
        top_contacts = Contact.query.filter(
            Contact.workspace_id == workspace_id,
            Contact.is_deleted == False,
            Contact.lead_score >= 70
        ).order_by(Contact.lead_score.desc()).limit(5).all()

        for c in top_contacts:
            insights['high_value_contacts'].append({
                'id': c.id,
                'name': c.full_name,
                'score': c.lead_score,
                'insight': c.ai_insight or '',
                'company': c.company.name if c.company else ''
            })

        # Negative sentiment conversations
        neg_convs = Conversation.query.filter(
            Conversation.workspace_id == workspace_id,
            Conversation.ai_sentiment == 'negative',
            Conversation.status == 'open'
        ).order_by(Conversation.ai_sentiment_score.asc()).limit(5).all()

        for conv in neg_convs:
            insights['negative_conversations'].append({
                'id': conv.id,
                'customer': conv.customer.profile_name if conv.customer else '',
                'sentiment_score': conv.ai_sentiment_score,
                'summary': conv.ai_summary or ''
            })

        # Summary stats
        total_open = Deal.query.filter_by(workspace_id=workspace_id, status='open', is_deleted=False).count()
        scored = Deal.query.filter(
            Deal.workspace_id == workspace_id,
            Deal.status == 'open',
            Deal.is_deleted == False,
            Deal.ai_score.isnot(None)
        ).count()
        avg_score = db.session.query(func.avg(Deal.ai_score)).filter(
            Deal.workspace_id == workspace_id,
            Deal.status == 'open',
            Deal.is_deleted == False,
            Deal.ai_score.isnot(None)
        ).scalar() or 0

        insights['summary'] = {
            'total_open_deals': total_open,
            'scored_deals': scored,
            'avg_deal_score': round(float(avg_score), 1),
            'stale_count': len(stale_deals),
            'hot_count': len(hot_deals),
            'cold_count': len(cold_deals),
        }

        return insights


def _call_ai_simple(prompt, ai_client, model_name, provider='gemini'):
    """Simple AI call that returns raw text."""
    from google.genai import types
    
    if provider == 'gemini':
        resp = ai_client.models.generate_content(
            model=model_name,
            contents=[{'role': 'user', 'parts': [{'text': prompt}]}],
            config=types.GenerateContentConfig(
                system_instruction="Sen bir CRM veri analisti olarak JSON formatinda yanit veriyorsun. Sadece JSON don, baska hicbir sey yazma.",
                temperature=0.3
            )
        )
        return resp.text
    elif provider == 'anthropic':
        resp = ai_client.messages.create(
            model=model_name,
            max_tokens=512,
            system="Sen bir CRM veri analisti olarak JSON formatinda yanit veriyorsun. Sadece JSON don, baska hicbir sey yazma.",
            messages=[{'role': 'user', 'content': prompt}]
        )
        return resp.content[0].text
    return ''


def _parse_json(text):
    """Parse JSON from AI response, handling markdown fences."""
    if not text:
        return None
    clean = text.strip()
    if clean.startswith('```'):
        clean = clean.split('\n', 1)[-1]
        clean = clean.rsplit('```', 1)[0].strip()
    try:
        return json.loads(clean)
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"Failed to parse AI JSON: {clean[:200]}")
        return None
