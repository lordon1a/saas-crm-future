# Otomasyon & Workflow Sistemi - Kullanım Kılavuzu

## 🎯 Genel Bakış

WhatsApp CRM'e eklenen otomasyon sistemi, tekrarlayan görevleri otomatikleştirerek iş yükünüzü azaltır ve müşteri deneyimini iyileştirir.

## 📦 Kurulum

### 1. Migration Çalıştırın

```bash
python migrate_automation.py
```

Bu komut şu tabloları oluşturur:
- `automation_rules` - Otomasyon kuralları
- `automation_executions` - Çalıştırma geçmişi
- `scheduled_messages` - Zamanlanmış mesajlar
- `auto_replies` - Otomatik yanıtlar
- `assignment_rules` - Atama kuralları
- `workflow_templates` - Workflow şablonları

### 2. Sunucuyu Yeniden Başlatın

```bash
python app.py
```

## 🤖 Özellikler

### 1. Otomatik Yanıtlar (Auto-Reply)

Belirli anahtar kelimelere otomatik yanıt verir.

**Kullanım Senaryoları:**
- "Fiyat" yazana fiyat listesi gönder
- "Çalışma saatleri" yazana mesai bilgisi ver
- "IBAN" yazana hesap bilgilerini gönder

**API Endpoint:**
```
GET    /api/automation/auto-replies
POST   /api/automation/auto-replies
PUT    /api/automation/auto-replies/:id
DELETE /api/automation/auto-replies/:id
```

**Örnek Oluşturma:**
```json
{
  "name": "Fiyat Bilgisi",
  "keywords": "fiyat, ücret, ne kadar",
  "match_type": "contains",
  "case_sensitive": false,
  "reply_message": "Fiyat listemiz için: https://example.com/fiyatlar",
  "reply_delay": 2,
  "is_active": true
}
```

**Match Types:**
- `contains` - İçerir (varsayılan)
- `exact` - Tam eşleşme
- `starts_with` - İle başlar
- `ends_with` - İle biter

---

### 2. Otomatik Atama (Auto-Assignment)

Yeni konuşmaları otomatik olarak temsilcilere atar.

**Atama Stratejileri:**
- `round_robin` - Sırayla atama
- `load_based` - En az yükü olana atama
- `specific_agent` - Belirli bir temsilciye atama

**API Endpoint:**
```
GET    /api/automation/assignment-rules
POST   /api/automation/assignment-rules
PUT    /api/automation/assignment-rules/:id
DELETE /api/automation/assignment-rules/:id
```

**Örnek: Round-Robin Atama**
```json
{
  "name": "VIP Müşteri Atama",
  "is_active": true,
  "priority": 10,
  "conditions": {
    "customer_tags": ["VIP"]
  },
  "assignment_type": "round_robin",
  "assignment_config": {
    "agent_ids": [1, 2, 3]
  }
}
```

**Örnek: Load-Based Atama**
```json
{
  "name": "Genel Atama",
  "is_active": true,
  "priority": 0,
  "assignment_type": "load_based",
  "assignment_config": {
    "agent_ids": [1, 2, 3, 4]
  }
}
```

---

### 3. Zamanlanmış Mesajlar (Scheduled Messages)

Belirli bir tarih/saatte veya tekrarlayan şekilde mesaj gönderir.

**Kullanım Senaryoları:**
- Randevu hatırlatmaları
- Kampanya duyuruları
- Takip mesajları
- Doğum günü kutlamaları

**API Endpoint:**
```
GET    /api/automation/scheduled-messages
POST   /api/automation/scheduled-messages
DELETE /api/automation/scheduled-messages/:id
```

**Örnek: Tek Seferlik Mesaj**
```json
{
  "target_type": "conversation",
  "target_id": 123,
  "message_body": "Randevunuz yarın saat 14:00'te. Görüşmek üzere!",
  "schedule_type": "once",
  "scheduled_at": "2024-03-20T14:00:00Z"
}
```

**Örnek: Tekrarlayan Mesaj**
```json
{
  "target_type": "segment",
  "target_segment": "VIP",
  "message_body": "Haftalık özel kampanyalarımızı kaçırmayın!",
  "schedule_type": "recurring",
  "scheduled_at": "2024-03-18T10:00:00Z",
  "recurrence_pattern": "weekly",
  "recurrence_config": {
    "days": [1],
    "time": "10:00"
  }
}
```

---

### 4. Otomasyon Kuralları (Automation Rules)

Karmaşık iş akışları oluşturun.

**Trigger Types:**
- `new_conversation` - Yeni konuşma başladığında
- `keyword` - Belirli kelime geldiğinde
- `tag_added` - Etiket eklendiğinde
- `time_based` - Belirli zamanda
- `inactivity` - Belirli süre aktivite olmadığında

**Actions:**
- `send_message` - Mesaj gönder
- `assign_agent` - Temsilci ata
- `add_tag` - Etiket ekle
- `create_ticket` - Ticket oluştur (gelecekte)
- `send_notification` - Bildirim gönder (gelecekte)
- `update_customer` - Müşteri bilgilerini güncelle

**API Endpoint:**
```
GET    /api/automation/rules
POST   /api/automation/rules
PUT    /api/automation/rules/:id
DELETE /api/automation/rules/:id
POST   /api/automation/rules/:id/toggle
```

**Örnek: Yeni Müşteri Hoş Geldin**
```json
{
  "name": "Yeni Müşteri Hoş Geldin",
  "description": "Yeni konuşma başladığında hoş geldin mesajı gönder",
  "is_active": true,
  "trigger_type": "new_conversation",
  "trigger_config": {},
  "conditions": {},
  "actions": [
    {
      "type": "send_message",
      "message": "Merhaba! Size nasıl yardımcı olabilirim?"
    },
    {
      "type": "assign_agent",
      "strategy": "round_robin"
    }
  ]
}
```

**Örnek: Sipariş Takibi**
```json
{
  "name": "Sipariş Onay Mesajı",
  "description": "Yeni sipariş etiketlendiğinde onay mesajı gönder",
  "is_active": true,
  "trigger_type": "tag_added",
  "trigger_config": {
    "tag": "yeni_siparis"
  },
  "conditions": {},
  "actions": [
    {
      "type": "send_message",
      "message": "Siparişiniz alındı! Sipariş numaranız: #{{order_id}}"
    },
    {
      "type": "add_tag",
      "tag": "siparis_onaylandi"
    }
  ]
}
```

**Örnek: Mesai Dışı Otomatik Yanıt**
```json
{
  "name": "Mesai Dışı Yanıt",
  "description": "Mesai saatleri dışında otomatik yanıt",
  "is_active": true,
  "trigger_type": "new_conversation",
  "trigger_config": {},
  "conditions": {
    "time_range": {
      "start": 18,
      "end": 9
    }
  },
  "actions": [
    {
      "type": "send_message",
      "message": "Mesai saatlerimiz dışındasınız. Hafta içi 09:00-18:00 arası size yardımcı olabiliriz."
    }
  ]
}
```

---

### 5. Workflow Templates

Hazır workflow şablonları kullanarak hızlıca başlayın.

**API Endpoint:**
```
GET /api/automation/workflow-templates
```

**Sistem Şablonları:**
1. **Yeni Müşteri Hoş Geldin** - Onboarding
2. **Sipariş Takibi** - Sales
3. **Destek Talebi Yönlendirme** - Support

---

## 📊 İstatistikler

Otomasyon performansını takip edin.

**API Endpoint:**
```
GET /api/automation/stats
```

**Dönen Veriler:**
```json
{
  "rules": {
    "total": 5,
    "active": 4
  },
  "auto_replies": {
    "total": 8,
    "active": 6
  },
  "assignment_rules": {
    "total": 3,
    "active": 3
  },
  "executions_30d": 1250,
  "success_rate": 98.4
}
```

---

## 🔧 Teknik Detaylar

### Webhook Entegrasyonu

Otomasyon sistemi webhook handler'a entegre edilmiştir:

```python
# services/webhook_handler.py

# Otomatik yanıt kontrolü
AutoReplyEngine.check_and_reply(message, conversation)

# Otomatik atama (eğer atanmamışsa)
if not conversation.assigned_to:
    AssignmentEngine.auto_assign_conversation(conversation)
```

### Execution Flow

1. **Webhook** → Yeni mesaj gelir
2. **Auto-Reply Engine** → Keyword kontrolü yapar
3. **Assignment Engine** → Atama kurallarını kontrol eder
4. **Automation Engine** → Diğer kuralları çalıştırır
5. **Database** → Execution log kaydedilir

### Koşul Sistemi

Tüm otomasyon türleri koşul destekler:

```json
{
  "conditions": {
    "customer_tags": ["VIP", "Kurumsal"],
    "conversation_tags": ["yeni_siparis"],
    "time_range": {
      "start": 9,
      "end": 18
    },
    "weekdays": [0, 1, 2, 3, 4]
  }
}
```

---

## 🎯 Kullanım Örnekleri

### Örnek 1: E-ticaret Otomasyonu

```javascript
// 1. Yeni sipariş geldiğinde
{
  "trigger_type": "tag_added",
  "trigger_config": {"tag": "yeni_siparis"},
  "actions": [
    {"type": "send_message", "message": "Siparişiniz alındı!"},
    {"type": "assign_agent", "agent_id": 5}
  ]
}

// 2. Kargo bilgisi
{
  "trigger_type": "tag_added",
  "trigger_config": {"tag": "kargolandi"},
  "actions": [
    {"type": "send_message", "message": "Kargonuz yola çıktı! Takip no: {{tracking}}"}
  ]
}

// 3. Ödeme hatırlatma (zamanlanmış)
{
  "target_type": "conversation",
  "message_body": "Ödeme bekliyoruz. IBAN: TR00...",
  "scheduled_at": "2024-03-20T10:00:00Z"
}
```

### Örnek 2: Destek Otomasyonu

```javascript
// 1. Destek talebi yönlendirme
{
  "trigger_type": "keyword",
  "trigger_config": {"keywords": ["destek", "yardım", "sorun"]},
  "actions": [
    {"type": "add_tag", "tag": "destek_talebi"},
    {"type": "assign_agent", "strategy": "load_based"}
  ]
}

// 2. Otomatik FAQ yanıtları
{
  "keywords": "iade, geri gönderim",
  "reply_message": "İade politikamız: 14 gün içinde..."
}

// 3. Takip mesajı (24 saat sonra)
{
  "trigger_type": "inactivity",
  "trigger_config": {"hours": 24},
  "actions": [
    {"type": "send_message", "message": "Sorununuz çözüldü mü?"}
  ]
}
```

### Örnek 3: Satış Otomasyonu

```javascript
// 1. Lead scoring
{
  "trigger_type": "keyword",
  "trigger_config": {"keywords": ["fiyat", "satın al", "sipariş"]},
  "actions": [
    {"type": "update_customer", "updates": {"labels": "Potansiyel"}},
    {"type": "assign_agent", "agent_id": 3}
  ]
}

// 2. Follow-up (3 gün sonra)
{
  "target_type": "segment",
  "target_segment": "Potansiyel",
  "message_body": "Ürünlerimiz hakkında daha fazla bilgi almak ister misiniz?",
  "scheduled_at": "+3 days"
}
```

---

## 🚀 Best Practices

### 1. Öncelik Sıralaması

Atama kurallarında priority kullanın:
- VIP müşteriler: priority 10
- Kurumsal: priority 5
- Genel: priority 0

### 2. Koşul Kullanımı

Gereksiz çalıştırmaları önlemek için koşul ekleyin:
- Zaman aralığı (mesai saatleri)
- Müşteri etiketleri
- Hafta günleri

### 3. Gecikme Ekleyin

Otomatik yanıtlara 1-3 saniye gecikme ekleyin (daha doğal görünür):
```json
{
  "reply_delay": 2
}
```

### 4. Test Edin

Yeni kuralları önce test modunda çalıştırın:
```json
{
  "is_active": false
}
```

### 5. İstatistikleri Takip Edin

Düzenli olarak execution loglarını kontrol edin:
```
GET /api/automation/stats
```

---

## 🐛 Sorun Giderme

### Otomatik Yanıt Çalışmıyor

1. Kural aktif mi? (`is_active: true`)
2. Keyword doğru mu?
3. Match type uygun mu?
4. Koşullar sağlanıyor mu?
5. WhatsApp API yapılandırılmış mı?

### Atama Çalışmıyor

1. Atama kuralı aktif mi?
2. Agent ID'ler doğru mu?
3. Koşullar sağlanıyor mu?
4. Priority sıralaması doğru mu?

### Zamanlanmış Mesaj Gönderilmedi

1. Scheduled message worker çalışıyor mu?
2. Tarih formatı doğru mu?
3. Status "pending" mi?
4. WhatsApp API yapılandırılmış mı?

---

## 📝 Gelecek Özellikler

- [ ] Visual workflow builder (drag & drop)
- [ ] A/B testing
- [ ] Advanced conditions (AND/OR logic)
- [ ] Webhook triggers
- [ ] Email automation
- [ ] SMS automation
- [ ] AI-powered responses
- [ ] Sentiment analysis triggers

---

## 🔗 İlgili Dokümantasyon

- [FEATURES.md](FEATURES.md) - Tüm özellikler
- [ROADMAP.md](ROADMAP.md) - Gelecek planları
- [API Documentation](#) - API referansı

---

## 💡 Destek

Sorularınız için:
- GitHub Issues
- Dokümantasyon
- Test: `python test_automation.py`
