# CRM Eksiklik Kapatma Planı

Kritik ve önemli tüm CRM eksikliklerini 3 fazda kapatır; her özellik için model, servis, route ve UI detayları belirtilmiştir.

---

## FAZ 1 — Mevcut Modüllerin Tamamlanması (1–2 hafta)

### 1.1 Email Sequence — Enrollment + Reply Detection

**Sorun:** `EmailSequence` / `EmailSequenceStep` modelleri var, `create_sequence` servisi var; ancak kişi bir sequence'a kayıt edilemiyor, adımlar otomatik çalışmıyor, cevap gelince durmuyor.

**Yeni Model — `EmailSequenceEnrollment` (`email_sequence_enrollments`)**
```python
id, workspace_id, sequence_id → FK(email_sequences),
contact_id → FK(contacts), enrolled_by → FK(users),
status: 'active' | 'paused' | 'completed' | 'stopped',
current_step_index: int (0-tabanlı),
next_send_at: DateTime,          # bir sonraki adım ne zaman gönderilecek
stopped_reason: str nullable,    # 'reply_detected' | 'manual' | 'bounced'
enrolled_at, completed_at
```
Migration: `migrations/add_email_sequence_enrollment.py`

**`services/email_hub_service.py` — Yeni Fonksiyonlar**
```python
enroll_contact(workspace_id, sequence_id, contact_id, enrolled_by)
  → EmailSequenceEnrollment oluştur, next_send_at = now + step[0].delay_hours
  → aynı contact aynı sequence'ta zaten active ise hata döndür

process_enrollment_queue()       # APScheduler her 15 dk çağırır
  → next_send_at <= now olan active enrollment'ları çek
  → queue_outbound_email() ile step emailini gönder
  → current_step_index++, next_send_at = now + next_step.delay_hours
  → son adımsa status='completed'

unenroll_contact(enrollment_id, reason)
  → status='stopped', stopped_reason=reason

process_reply(workspace_id, from_email, in_reply_to_message_id)
  → OutboundEmail'de matching message_id bul
  → ilgili contact'ın active enrollment'larını bul
  → unenroll_contact(..., reason='reply_detected') çağır
```

**`services/gmail_sync_service.py` — Değişiklik**
- `sync_recent_emails()` içinde her gelen mail için `In-Reply-To` ve `References` header'larını yakala
- `EmailHubService.process_reply()` çağır

**APScheduler (`services/task_scheduler.py`)**
```python
# Her 15 dakikada bir
scheduler.add_job(EmailHubService.process_enrollment_queue, 'interval', minutes=15)
```

**`routes/email_hub.py` — Yeni Endpoint'ler**
```
POST /api/v1/email-hub/sequences/<id>/enroll      body: {contact_id}
DELETE /api/v1/email-hub/enrollments/<id>          unenroll
GET  /api/v1/email-hub/sequences/<id>/enrollments  kayıt listesi
GET  /api/v1/email-hub/contacts/<id>/enrollments   kişinin tüm kayıtları
```

**UI**
- Email Hub → Sequences sekmesi → her sequence kartında "Kişi Ekle" butonu
- Contact detay sayfası → Timeline sekmesi yanına "Sequence" rozeti
- Enrollment durumu: yeşil (active) / sarı (paused) / kırmızı (stopped)

---

### 1.2 Workflow Re-enrollment Kontrolü

**Sorun:** `trigger_event()` her tetiklendiğinde aynı kişiyi aynı workflow ile yeniden çalıştırıyor — production'da spam riski.

**`models_crm.py` — İki Değişiklik**

1. `WorkflowAutomation`'a yeni kolon:
```python
re_enrollment_mode = db.Column(
    db.String(30), default='always', nullable=False
)
# Değerler: 'always' | 'never' | 'once_per_day' | 'once_per_week'
```

2. Yeni model `WorkflowEnrollment` (`workflow_enrollments`):
```python
id, workflow_id → FK(workflow_automations),
workspace_id, entity_id: int, entity_type: str,
enrolled_at: DateTime, completed_at: DateTime nullable,
status: 'running' | 'completed' | 'failed'
```
Migration: `migrations/add_workflow_enrollment.py`

**`services/workflow_service.py` — `trigger_event()` Değişikliği**
```python
# workflows döngüsünde, execute'dan önce:
if not WorkflowService._check_enrollment_allowed(workflow, entity_type, entity_id):
    continue

def _check_enrollment_allowed(workflow, entity_type, entity_id) -> bool:
    mode = workflow.re_enrollment_mode
    if mode == 'always':
        return True
    last = WorkflowEnrollment.query.filter_by(
        workflow_id=workflow.id, entity_id=entity_id, entity_type=entity_type
    ).order_by(WorkflowEnrollment.enrolled_at.desc()).first()
    if mode == 'never':
        return last is None
    if mode == 'once_per_day':
        return not last or (datetime.utcnow() - last.enrolled_at).days >= 1
    if mode == 'once_per_week':
        return not last or (datetime.utcnow() - last.enrolled_at).days >= 7
```

**Workflow Builder UI — Settings Paneli**
- Workflow canvas sağ panelinde "Tetikleyici Ayarları" bölümüne `re_enrollment_mode` dropdown ekle
- Seçenekler: Her seferinde / Yalnızca ilk kez / Günde en fazla 1 kez / Haftada en fazla 1 kez

---

### 1.3 Özelleştirilebilir Raporlama Dashboard'u

**Sorun:** `analytics.py` sabit endpoint'ler döndürüyor; kullanıcı hangi widget'ı nerede göreceğini seçemiyor.

**Yeni Model — `DashboardWidget` (`dashboard_widgets`)**
```python
id, workspace_id, user_id → FK(users),
widget_type: str,   # 'kpi_card' | 'bar_chart' | 'funnel' | 'pie_chart'
                    # | 'leaderboard' | 'activity_feed' | 'goal_progress' | 'heatmap'
title: str,
config_json: Text,  # widget'a özel ayarlar (metrik türü, tarih aralığı, pipeline filtresi)
pos_x: int, pos_y: int, width: int, height: int,
created_at, updated_at
```
Migration: `migrations/add_dashboard_widgets.py`

**`config_json` Şeması (widget tipine göre)**
```json
// kpi_card
{"metric": "total_revenue" | "won_deals" | "open_deals" | "avg_deal_value",
 "period": "this_month" | "last_30_days" | "this_quarter" | "this_year",
 "pipeline_id": null}

// bar_chart
{"metric": "revenue_by_month" | "deals_by_stage" | "tasks_by_assignee",
 "period": "last_6_months", "pipeline_id": null}

// leaderboard
{"metric": "won_deals" | "revenue" | "tasks_completed",
 "period": "this_month", "limit": 10}
```

**`routes/analytics.py` — Yeni Endpoint'ler**
```
GET  /api/v1/analytics/widgets          kullanıcının widget listesi
POST /api/v1/analytics/widgets          yeni widget oluştur
PATCH /api/v1/analytics/widgets/<id>    config veya pozisyon güncelle
DELETE /api/v1/analytics/widgets/<id>   widget sil
POST /api/v1/analytics/widgets/reorder  toplu pozisyon güncelle (drag sonrası)
GET  /api/v1/analytics/widget-data/<id> widget verisini getir (mevcut AnalyticsService'i çağırır)
```

**Frontend — Analytics sayfası**
- `react-grid-layout` paketi ile sürükle-bırak grid
- Sağ üst "Widget Ekle" butonu → tip ve metrik seçimi modal
- Her widget sağ üst köşesinde ⚙️ (config) ve ✕ (sil) butonları
- Layout her değişimde `/widgets/reorder` ile kaydedilir

---

## FAZ 2 — Kritik Yeni Modüller (2–4 hafta)

### 2.1 Dinamik Liste / Segment Sistemi

**Sorun:** `FilterService` ve `SavedFilterService` var, kişileri filtreleye biliyor; ancak "Bu filtreye uyan kişiler" listesi yok — üyelik takip edilmiyor, workflow'larda tetikleyici olarak kullanılamıyor.

**Yeni Modeller (`models_crm.py`)**

`ContactSegment` (`contact_segments`):
```python
id, workspace_id, created_by → FK(users),
name: str(200), description: str(500),
is_dynamic: bool default True,   # False = manuel liste
filter_json: Text,               # FilterService formatı
member_count: int default 0,
last_synced_at: DateTime nullable,
created_at, updated_at
```

`SegmentMembership` (`segment_memberships`):
```python
id, segment_id → FK(contact_segments), contact_id → FK(contacts),
added_at: DateTime, removed_at: DateTime nullable,
is_current: bool default True
UniqueConstraint(segment_id, contact_id)
```
Migration: `migrations/add_contact_segments.py`

**`services/segment_service.py` — Yeni Servis**
```python
create_segment(workspace_id, user_id, name, description, filter_json, is_dynamic)
sync_segment(segment_id)
  → filter_json'u FilterService.apply_filters()'a ver (tüm kayıtlar, paginate yok)
  → mevcut üyeler vs yeni sonuç set → delta hesapla
  → yeni üyeler: SegmentMembership INSERT + WorkflowService.trigger_event('segment_joined')
  → çıkan üyeler: removed_at=now, is_current=False + trigger_event('segment_left')
  → segment.member_count güncelle, last_synced_at=now

sync_all_dynamic_segments(workspace_id)   # scheduler tarafından çağrılır

add_contact_manually(segment_id, contact_id)   # is_dynamic=False segmentler için
remove_contact_manually(segment_id, contact_id)
```

**APScheduler**
```python
scheduler.add_job(SegmentService.sync_all_dynamic_segments_globally,
                  'interval', minutes=30)
# sync_all_dynamic_segments_globally: tüm workspace'lerin segmentlerini sync et
```

**`routes/segments.py` — Yeni Route Dosyası**
```
GET    /api/v1/segments                    liste
POST   /api/v1/segments                    oluştur
GET    /api/v1/segments/<id>               detay + üyeler (sayfalı)
PATCH  /api/v1/segments/<id>               güncelle
DELETE /api/v1/segments/<id>               sil
POST   /api/v1/segments/<id>/sync          manuel senkronize et
POST   /api/v1/segments/<id>/members       manuel üye ekle
DELETE /api/v1/segments/<id>/members/<cid> manuel üye çıkar
GET    /api/v1/contacts/<id>/segments      kişinin üye olduğu segmentler
```

**Workflow Trigger Eklemeleri (`workflow_service.py` + `workflow_node_handlers.py`)**
```python
'segment_joined': 'Kişi segmente eklendi'
'segment_left':   'Kişi segmentten çıktı'
# trigger_config: {'segment_id': 42}
```

**UI**
- Sol navigasyonda Contacts altında "Segmentler" sayfası
- Segment oluşturma: isim + filtre builder (mevcut filter UI'ı yeniden kullan) + is_dynamic toggle
- Segment detay: üye listesi (contact kartları), son senkronizasyon zamanı, "Şimdi Senkronize Et" butonu
- Contact detay sayfasında "Segmentler" rozeti

---

### 2.2 Meeting Scheduler (Self-Booking Link)

**Sorun:** Takvim görünümü var, ama dışarıdan erişilebilen randevu booking linki yok.

**Yeni Modeller (`models_crm.py`)**

`MeetingLink` (`meeting_links`):
```python
id, workspace_id, user_id → FK(users),
slug: str(100) unique,              # URL'de kullanılır: /book/ali-satis
title: str(200),
duration_minutes: int default 30,  # 15 | 30 | 45 | 60
buffer_minutes: int default 0,     # toplantılar arası boşluk
max_days_ahead: int default 60,    # şu andan kaç gün ileriye bakılır
availability_json: Text,           # haftalık program
# {"monday": [{"start":"09:00","end":"17:00"}], "tuesday": [...], ...}
location: str nullable,            # "Zoom" | "Ofis" | özel
description: Text nullable,
is_active: bool default True,
created_at
```

`MeetingBooking` (`meeting_bookings`):
```python
id, meeting_link_id → FK(meeting_links), workspace_id,
contact_id → FK(contacts) nullable,   # CRM'de eşleşirse doldurulur
booker_name: str, booker_email: str, booker_notes: Text nullable,
start_time: DateTime, end_time: DateTime,
status: 'confirmed' | 'cancelled' | 'no_show',
google_calendar_event_id: str nullable,
zoom_meeting_url: str nullable,
confirmation_token: str,             # iptal linkinde kullanılır
created_at
```
Migration: `migrations/add_meeting_links.py`

**`services/meeting_link_service.py` — Yeni Servis**
```python
get_available_slots(meeting_link_id, date_from, date_to) -> List[datetime]
  → availability_json'dan çalışma saatlerini al
  → Google Calendar API ile user'ın mevcut etkinliklerini çek
  → buffer dahil çakışan slotları çıkar
  → duration'a uygun boş slotları listele

create_booking(meeting_link_id, booker_name, booker_email, start_time, notes)
  → MeetingBooking oluştur
  → Google Calendar'da etkinlik yarat (attendee: booker + owner)
  → booker'a onay emaili gönder (queue_outbound_email)
  → CRM'de Contact eşleştir veya oluştur
  → Activity olarak kaydet

cancel_booking(booking_id, token)
  → Google Calendar etkinliğini iptal et
  → booker'a iptal emaili gönder
  → status='cancelled'
```

**`routes/meeting_links.py` — Yeni Route Dosyası**
```
# CRM içi (auth gerekli)
GET    /api/v1/meeting-links                  kullanıcının linkleri
POST   /api/v1/meeting-links                  yeni link oluştur
PATCH  /api/v1/meeting-links/<id>             güncelle
DELETE /api/v1/meeting-links/<id>             sil
GET    /api/v1/meeting-links/<id>/bookings    rezervasyonlar

# Public (auth gerektirmez)
GET    /book/<slug>                           booking sayfası (Jinja template)
GET    /api/v1/public/book/<slug>/slots       boş slotlar (query: date_from, date_to)
POST   /api/v1/public/book/<slug>            rezervasyon oluştur
POST   /api/v1/public/book/cancel/<token>    rezervasyon iptal
```

**Templates**
- `templates/public/booking.html` — takvim görünümü (günlük slot grid), form
- Otomatik onay emaili şablonu

**UI (CRM içi)**
- Ayarlar → "Meeting Linkleri" sayfası
- Link oluşturma: başlık, süre, müsaitlik takvimi (haftalık grid), lokasyon
- Her linkin paylaşım URL'i + kopyala butonu
- Contact detay sayfası → "Toplantı Planla" → meeting link seç → `/book/<slug>?email=...` yeni sekmede aç

---

### 2.3 Form Builder (Web Formu → CRM)

**Sorun:** CRM'e dışarıdan lead girişi için hiç form altyapısı yok.

**Yeni Modeller (`models_crm.py`)**

`WebForm` (`web_forms`):
```python
id, workspace_id, created_by → FK(users),
name: str(200),
fields_json: Text,        # alan tanımları listesi (tip, label, required, options)
submit_action: str,       # 'create_contact' | 'update_contact' | 'create_deal'
redirect_url: str nullable,
notify_user_id → FK(users) nullable,   # submission gelince bildirim
is_active: bool default True,
submission_count: int default 0,
created_at, updated_at
```

`fields_json` Şeması:
```json
[
  {"id":"f1","type":"text","label":"Ad","field_map":"first_name","required":true},
  {"id":"f2","type":"email","label":"Email","field_map":"email","required":true},
  {"id":"f3","type":"tel","label":"Telefon","field_map":"phone","required":false},
  {"id":"f4","type":"select","label":"İlgi Alanı","field_map":"custom.interest",
   "options":["Satış","Destek","Demo"],"required":false},
  {"id":"f5","type":"textarea","label":"Mesaj","field_map":"note","required":false}
]
```

`FormSubmission` (`form_submissions`):
```python
id, form_id → FK(web_forms), workspace_id,
data_json: Text,                        # ham form verisi
contact_id → FK(contacts) nullable,     # eşleşen/oluşturulan contact
ip_address: str(50) nullable,
user_agent: str(500) nullable,
created_at
```
Migration: `migrations/add_web_forms.py`

**`services/form_service.py` — Yeni Servis**
```python
process_submission(form_id, data_dict, ip, user_agent)
  → WebForm al, is_active kontrol et
  → required alan validasyonu
  → email ile mevcut Contact ara → yoksa oluştur, varsa güncelle (merge logic)
  → FormSubmission kaydet, WebForm.submission_count++
  → notify_user_id varsa bildirim gönder
  → WorkflowService.trigger_event('form_submitted', 'contact', contact.id,
      context={'form_id': form_id, 'form_data': data_dict})
  → redirect_url döndür

validate_form_data(form_fields, submitted_data) -> (bool, List[str])  # hata listesi
```

**`routes/forms.py` — Yeni Route Dosyası**
```
# CRM içi (auth gerekli)
GET    /api/v1/forms                         form listesi
POST   /api/v1/forms                         oluştur
GET    /api/v1/forms/<id>                    detay
PATCH  /api/v1/forms/<id>                    güncelle
DELETE /api/v1/forms/<id>                    sil
GET    /api/v1/forms/<id>/submissions        gönderimler (sayfalı)
GET    /api/v1/forms/<id>/embed-code         <script> embed kodu döndür

# Public (auth gerektirmez, CSRF muaf)
GET    /f/<form_id>                          form sayfası (Jinja template)
POST   /api/v1/public/forms/<form_id>/submit gönderim
```

**Embed Kodu Formatı**
```html
<script src="https://domain.com/static/form-embed.js"
        data-form-id="abc123"
        data-theme="light"></script>
```
`form-embed.js`: shadow DOM ile iframe-free form render eder.

**Workflow Trigger**
```python
'form_submitted': 'Form gönderildi'
# trigger_config: {'form_id': 5}
```

**UI**
- Sol nav → "Formlar" yeni sayfası
- Form builder: sol panel (alan tipleri palette) + orta (form önizleme, sürükle-bırak sıralama) + sağ (alan ayarları)
- Alan tipleri: Text, Email, Telefon, Select, Checkbox, Textarea, Sayı, Tarih
- "Yayınla" → embed kodu + direkt link
- Submissions sekmesi: tablo görünümü, CSV export

---

### 2.4 Email Drag-and-Drop Template Editor

**Sorun:** Mevcut email şablonları düz metin/HTML; görsel blok editör yok.

**`models_crm.py` — `EmailTemplate` Değişikliği**
```python
# Mevcut alanlara ek:
design_json = db.Column(db.Text, nullable=True)
# Unlayer'ın exportDesign() çıktısı — HTML bu JSON'dan render edilir
editor_type = db.Column(db.String(20), default='html')
# 'html' (mevcut) | 'visual' (yeni Unlayer editörü)
```
Migration: `migrations/add_email_template_design_json.py`

**`routes/templates.py` — Değişiklikler**
- `POST/PATCH /api/v1/templates` — `design_json` ve `editor_type` alanlarını kaydet
- `GET /api/v1/templates/<id>` — `design_json` döndür

**Frontend**
- npm: `react-email-editor` (Unlayer — ücretsiz tier)
- Template düzenleme sayfasına "Görsel" / "HTML" toggle
- Görsel modda Unlayer componenti; kaydet → `exportDesign()` → `design_json`, `exportHtml()` → `body_html`
- Mevcut HTML şablonları olduğu gibi çalışmaya devam eder (geriye dönük uyumluluk)

---

## FAZ 3 — Önemli Yeni Modüller (3–5 hafta)

### 3.1 Web Chat / Chatbot Widget

**Yeni Modeller (`models_crm.py`)**

`WebChatConfig` (`webchat_configs`):
```python
id, workspace_id unique,
widget_title: str default 'Merhaba 👋',
welcome_message: Text,
primary_color: str default '#7c3aed',
bot_name: str default 'Asistan',
collect_name: bool default True,
collect_email: bool default True,
is_active: bool default True,
auto_create_contact: bool default True
```

`ChatSession` (`chat_sessions`):
```python
id, workspace_id, contact_id → FK nullable,
visitor_id: str (fingerprint/cookie),
status: 'open' | 'assigned' | 'closed',
assigned_to → FK(users) nullable,
source_url: str, started_at, last_message_at
```

`ChatMessage` (`chat_messages`):
```python
id, session_id → FK(chat_sessions),
sender_type: 'visitor' | 'agent' | 'bot',
sender_id: int nullable,
content: Text,
created_at
```
Migration: `migrations/add_webchat.py`

**`routes/webchat.py` — Yeni Route Dosyası**
```
# Public
GET  /api/v1/public/chat/init           oturum başlat (visitor_id cookie)
POST /api/v1/public/chat/<session_id>/message   mesaj gönder
GET  /api/v1/public/chat/<session_id>/poll      yeni mesajları çek (long-poll)

# CRM içi (auth gerekli)
GET  /api/v1/webchat/sessions           açık oturumlar
GET  /api/v1/webchat/sessions/<id>/messages   mesaj geçmişi
POST /api/v1/webchat/sessions/<id>/reply  ajan yanıtı
POST /api/v1/webchat/sessions/<id>/close  kapat → activity log
GET  /api/v1/webchat/config             widget config
PATCH /api/v1/webchat/config            config güncelle
```

**Bot Akışı (kural tabanlı)**
```
1. "Merhaba! Sizi nasıl tanıyalım?" → ad al
2. "Email adresinizi alabilir miyiz?" → email al
3. Contact oluştur/eşleştir
4. "Bir temsilci sizi yakında arayacak." → session assigned agent'a ilet
5. Canlı agent yanıt verirse bot susar
```

**`static/webchat-widget.js`** — embed snippet
```html
<script src="https://domain.com/static/webchat-widget.js"
        data-workspace="abc123"></script>
```

**UI**
- Channels → "Web Chat" sekmesi: canlı oturumlar listesi, sağda mesajlaşma paneli
- Ayarlar → "Chat Widget" sayfası: renk, başlık, karşılama mesajı, embed kodu

---

### 3.2 Call Logging (Arama Kaydı)

**Yeni Model — `CallLog` (`call_logs`)**
```python
id, workspace_id, contact_id → FK nullable, deal_id → FK nullable,
logged_by → FK(users),
direction: 'inbound' | 'outbound',
phone_number: str(50),
duration_seconds: int default 0,
outcome: 'connected' | 'no_answer' | 'busy' | 'left_voicemail' | 'wrong_number',
notes: Text nullable,
recording_url: str nullable,      # Twilio/Vonage recording linki
external_call_id: str nullable,   # Twilio CallSid
called_at: DateTime,
created_at
```
Migration: `migrations/add_call_logs.py`

**`routes/calls.py` — Yeni Route Dosyası**
```
GET  /api/v1/calls                      çağrı listesi (filtreli, sayfalı)
POST /api/v1/calls                      manuel log oluştur
GET  /api/v1/calls/<id>                 detay
PATCH /api/v1/calls/<id>               not güncelle
DELETE /api/v1/calls/<id>              sil
GET  /api/v1/contacts/<id>/calls        kişinin arama geçmişi
POST /api/v1/webhooks/twilio/call       Twilio webhook (call end event)
GET  /api/v1/analytics/calls/summary   günlük/haftalık özet
```

**Contact Timeline Entegrasyonu**
- `Activity` tablosuna `activity_type='call'` eklenir (zaten destekleniyor)
- `CallLog` kaydedilince otomatik `Activity` da oluşturulur

**UI**
- Contact detay sayfası → "Arama Kaydı" butonu → modal: yön, süre, sonuç, not
- Tasks sayfasında "Aramalar" filtresi
- Analytics → "Arama Performansı" widget (üst arayan, toplam süre, bağlanma oranı)

---

### 3.3 Zoom / Google Meet Entegrasyonu

**`services/zoom_service.py` — Yeni Servis**
```python
get_oauth_url(workspace_id, user_id) -> str      # OAuth2 başlat
handle_oauth_callback(code, workspace_id, user_id) # token kaydet
create_meeting(user_id, topic, start_time, duration_minutes) -> dict
  # → zoom_join_url, zoom_meeting_id döndürür
get_recording(meeting_id) -> str | None           # recording URL
```

**`ZoomIntegration` Modeli (`zoom_integrations`)**
```python
id, workspace_id, user_id unique,
access_token: Text (encrypted), refresh_token: Text (encrypted),
token_expires_at: DateTime,
zoom_user_id: str, zoom_email: str,
is_active: bool
```
Migration: `migrations/add_zoom_integration.py`

**Meeting Scheduler Entegrasyonu**
- `MeetingLink`'e `video_provider: 'none' | 'zoom' | 'google_meet'` alanı ekle
- `create_booking()` → video_provider=='zoom' ise `ZoomService.create_meeting()` çağır
- Zoom URL → `MeetingBooking.zoom_meeting_url`'e kaydet, onay emailine ekle

**Routes**
```
GET  /api/v1/integrations/zoom/auth         OAuth URL
GET  /api/v1/integrations/zoom/callback     OAuth callback
DELETE /api/v1/integrations/zoom            bağlantıyı kes
POST /api/v1/webhooks/zoom/recording        recording hazır webhook
```

**UI**
- Ayarlar → Entegrasyonlar → "Zoom" kartı → "Bağla" butonu
- Meeting Link oluşturmada "Video Görüşme Ekle" seçeneği

---

### 3.4 LinkedIn Sales Navigator Entegrasyonu

**`services/linkedin_service.py` — Yeni Servis**
```python
get_oauth_url(workspace_id, user_id) -> str
handle_oauth_callback(code, workspace_id, user_id)
enrich_contact(contact_id) -> dict
  # LinkedIn People Search API ile profil bul
  # → title, company, location, profile_url, connection_degree döndür
search_by_email(email) -> dict | None
```

**`models_crm.py` — `Contact` Değişikliği**
```python
linkedin_url = db.Column(db.String(500), nullable=True)     # zaten var mı kontrol et
linkedin_enriched_at = db.Column(db.DateTime, nullable=True)
```

**`services/enrichment.py` — Değişiklik**
- Mevcut `enrich_contact()` fonksiyonuna LinkedIn kaynağı olarak `LinkedInService.enrich_contact()` ekle

**Routes**
```
GET  /api/v1/integrations/linkedin/auth
GET  /api/v1/integrations/linkedin/callback
POST /api/v1/contacts/<id>/enrich/linkedin   tek kişiyi LinkedIn'den zenginleştir
```

**UI**
- Contact detay sayfasında LinkedIn URL varsa "LinkedIn'de Görüntüle" butonu
- Enrichment bölümünde "LinkedIn'den Doldur" butonu

---

### 3.5 Facebook Lead Ads + Google Ads Bağlantısı

**Facebook Lead Ads**

`services/ads_sync_service.py` — `FacebookLeadAdsService`:
```python
verify_webhook(token, challenge) -> str        # Meta webhook doğrulama
process_lead_webhook(payload)
  # payload'dan: form_id, leadgen_id, ad_name, page_id
  # → Graph API ile lead alanlarını çek (ad, email, telefon, özel sorular)
  # → FormService.process_submission() ile CRM'e yönlendir
  # → lead_source = 'facebook_ads', utm_source kaydet
```

`FacebookAdsIntegration` Modeli:
```python
id, workspace_id, page_id, page_name,
access_token: Text (encrypted), webhook_subscribed: bool,
created_at
```

**Google Ads Conversion Tracking**

`services/ads_sync_service.py` — `GoogleAdsService`:
```python
send_conversion(workspace_id, deal_id, conversion_value)
  # Deal kazanılınca routes/pipeline.py'deki close_deal() çağırır
  # → Google Ads API'ye offline conversion event gönderir
  # → gclid (Google Click ID) contact'tan alınır (form ile yakalanmışsa)
```

**`Contact` Modeline Ekleme**
```python
utm_source, utm_medium, utm_campaign, utm_content  # zaten varsa kontrol et
gclid: str nullable      # Google Click ID
fbclid: str nullable     # Facebook Click ID
lead_source: str nullable  # 'facebook_ads' | 'google_ads' | 'form' | 'manual' | ...
```

**Routes**
```
GET  /api/v1/webhooks/facebook/lead          webhook doğrulama (GET)
POST /api/v1/webhooks/facebook/lead          lead geldi (POST)
GET  /api/v1/integrations/facebook/auth      OAuth
GET  /api/v1/integrations/facebook/callback  callback
GET  /api/v1/integrations/google-ads/auth    OAuth
```

**UI**
- Channels → "Reklam Entegrasyonları" sayfası
- Facebook bağlantısı + hangi sayfaların formları izlensin seçimi
- Google Ads bağlantısı + hangi conversion aksiyonu kullanılsın
- Analytics'e "Lead Kaynağı Dağılımı" pie chart widget

---

## Migration Listesi (Sırasıyla)

| # | Dosya | Ne Ekliyor |
|---|---|---|
| 1 | `add_email_sequence_enrollment.py` | `email_sequence_enrollments` tablosu |
| 2 | `add_workflow_enrollment.py` | `workflow_enrollments` + `WorkflowAutomation.re_enrollment_mode` |
| 3 | `add_dashboard_widgets.py` | `dashboard_widgets` tablosu |
| 4 | `add_contact_segments.py` | `contact_segments` + `segment_memberships` |
| 5 | `add_meeting_links.py` | `meeting_links` + `meeting_bookings` |
| 6 | `add_web_forms.py` | `web_forms` + `form_submissions` |
| 7 | `add_email_template_design_json.py` | `EmailTemplate.design_json` + `.editor_type` |
| 8 | `add_webchat.py` | `webchat_configs` + `chat_sessions` + `chat_messages` |
| 9 | `add_call_logs.py` | `call_logs` tablosu |
| 10 | `add_zoom_integration.py` | `zoom_integrations` tablosu |
| 11 | `add_contact_ads_fields.py` | `Contact.gclid/fbclid/lead_source/utm_*` |

---

## Uygulama Takvimi

| Faz | Özellikler | Tahmini Süre |
|---|---|---|
| **Faz 1** | Email enrollment + reply detection, Workflow re-enrollment, Dashboard widget | 1–2 hafta |
| **Faz 2** | Dinamik segmentler, Meeting scheduler, Form builder, Email görsel editör | 2–4 hafta |
| **Faz 3** | Web chat, Call logging, Zoom, LinkedIn, Facebook/Google Ads | 3–5 hafta |

**Toplam yeni dosya:** 8 route, 5 servis, 1 migration/özellik  
**Etkilenen mevcut dosya:** `models_crm.py`, `workflow_service.py`, `email_hub_service.py`, `gmail_sync_service.py`, `task_scheduler.py`, `routes/analytics.py`, `routes/templates.py`, `routes/pipeline.py`
