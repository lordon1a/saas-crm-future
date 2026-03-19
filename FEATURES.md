# WhatsApp CRM - Özellikler Dokümantasyonu

## 🎯 Tamamlanan Orta Öncelikli Özellikler

### 1. Analytics & Raporlama Dashboard

**Endpoint:** `GET /api/analytics`

**Özellikler:**
- KPI kartları (toplam konuşma, müşteri, mesaj sayıları)
- 14 günlük konuşma ve mesaj trendi grafiği
- Etiket dağılımı (pie chart)
- Müşteri büyüme trendi
- Temsilci performans tablosu
- Haftalık karşılaştırma metrikleri

**Kullanım:**
```javascript
const response = await fetch('/api/analytics');
const data = await response.json();
// data.kpis, data.trend, data.tag_distribution, data.agent_stats
```

**Sayfa:** `/analytics`

---

### 2. Broadcast (Toplu Mesaj Gönderimi)

**Endpoint:** `POST /api/broadcast/send`

**Özellikler:**
- Tüm müşterilere toplu mesaj
- Etikete göre segmentli gönderim
- Gerçek zamanlı önizleme
- Gönderim istatistikleri (başarılı/başarısız)
- Rate limiting koruması

**Kullanım:**
```javascript
const response = await fetch('/api/broadcast/send', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    target: 'tags',  // 'all' veya 'tags'
    tag: 'VIP',      // target='tags' ise zorunlu
    content: 'Merhaba! Özel kampanyamız başladı...'
  })
});
```

**Sayfa:** `/broadcast`

**Önemli Notlar:**
- WhatsApp API yapılandırması gereklidir
- Meta rate limit kurallarına uygun çalışır
- Her mesaj arasında 1 saniye bekleme süresi vardır

---

### 3. Mesaj Şablonları Yönetimi

**Endpoints:**
- `GET /api/settings/templates` - Tüm şablonları listele
- `POST /api/settings/templates` - Yeni şablon oluştur
- `PUT /api/settings/templates/:id` - Şablonu güncelle
- `DELETE /api/settings/templates/:id` - Şablonu sil

**Özellikler:**
- Özelleştirilebilir mesaj şablonları
- Kategori desteği (marketing, utility, custom)
- Çoklu dil desteği
- Değişken placeholder'ları ({{variable}})
- Workspace izolasyonu

**Şablon Yapısı:**
```json
{
  "name": "Sipariş Onayı",
  "body": "Siparişiniz alındı. Sipariş no: {{order_id}}",
  "category": "utility",
  "language": "tr"
}
```

**Kullanım Örneği:**
```javascript
// Şablon oluştur
await fetch('/api/settings/templates', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'Hoş Geldiniz',
    body: 'Merhaba {{name}}, aramıza hoş geldiniz!',
    category: 'custom',
    language: 'tr'
  })
});
```

**Sayfa:** `/settings` > Mesaj Şablonları sekmesi

---

### 4. Müşteri Segmentasyonu

**Endpoints:**
- `GET /api/contacts` - Tüm müşterileri listele
- `POST /api/customers` - Yeni müşteri ekle (etiketlerle)
- `PATCH /api/customers/:id` - Müşteri etiketlerini güncelle
- `POST /api/customers/bulk-delete` - Toplu silme

**Özellikler:**
- Müşteri etiketleme sistemi (labels)
- Etikete göre filtreleme
- Toplu işlemler (seçme, silme)
- Sütun görünürlük ayarları
- Gelişmiş arama (isim, telefon, e-posta, şirket)
- Durum filtreleme (aktif/pasif)

**Etiket Örnekleri:**
- VIP
- Potansiyel
- Kurumsal
- Bireysel
- Yeni Müşteri

**Kullanım:**
```javascript
// Etiketli müşteri oluştur
await fetch('/api/customers', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    phone_number: '+905551234567',
    profile_name: 'Ahmet Yılmaz',
    email: 'ahmet@example.com',
    labels: 'VIP, Kurumsal'
  })
});
```

**Sayfa:** `/contacts`

**Filtreleme:**
- Durum: Tüm Kişiler / Aktif Konuşmalar / Pasif Kişiler
- Etiket: Dropdown ile etiket seçimi
- Arama: Gerçek zamanlı arama (500ms debounce)

---

## 🔧 Teknik İyileştirmeler

### SSE (Server-Sent Events) Entegrasyonu

**Endpoint:** `GET /api/notifications/stream`

**Özellikler:**
- Gerçek zamanlı bildirimler
- Yeni mesaj geldiğinde otomatik güncelleme
- Bağlantı kopması durumunda otomatik yeniden bağlanma
- Workspace izolasyonu

**Frontend Kullanımı:**
```javascript
const eventSource = new EventSource('/api/notifications/stream');

eventSource.addEventListener('new_message', (e) => {
  const data = JSON.parse(e.data);
  // Konuşma listesini güncelle
  loadConversations();
  // Toast bildirimi göster
  showToast('Yeni mesaj geldi!');
});
```

---

### Workspace & Team Yönetimi

**Endpoints:**
- `GET /api/settings/workspace` - Workspace ayarları
- `PUT /api/settings/workspace` - Workspace güncelle
- `GET /api/settings/team` - Takım üyeleri
- `POST /api/settings/team` - Yeni üye ekle
- `DELETE /api/settings/team/:id` - Üye sil

**Özellikler:**
- Multi-tenant yapı
- WhatsApp API yapılandırması
- Takım üyesi yönetimi
- Rol bazlı erişim (admin/agent)

---

## 📊 Veritabanı Değişiklikleri

### Yeni Tablo: MessageTemplate

```sql
CREATE TABLE message_templates (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    body TEXT NOT NULL,
    category VARCHAR(50) DEFAULT 'custom',
    language VARCHAR(10) DEFAULT 'tr',
    created_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);
```

### Migration

Mevcut veritabanına yeni tabloyu eklemek için:

```bash
python migrate_add_templates.py
```

---

## 🧪 Test

Test scriptini çalıştırın:

```bash
# Önce sunucuyu başlatın
python app.py

# Başka bir terminalde test scriptini çalıştırın
python test_features.py
```

Test edilen özellikler:
- ✓ Analytics API
- ✓ Message Templates CRUD
- ✓ Broadcast endpoint
- ✓ Contacts & Segmentation
- ✓ Workspace settings
- ✓ Team management

---

## 📝 Seed Data

Örnek veriler oluşturmak için:

```bash
python seed_data.py
```

Oluşturulan veriler:
- Admin ve Agent kullanıcıları
- Örnek müşteriler
- Hızlı yanıtlar
- **Mesaj şablonları** (YENİ!)
  - Sipariş Onayı
  - Kargo Bildirimi
  - Ödeme Hatırlatma
  - Kampanya Duyurusu
  - Destek Talebi Alındı

---

## 🎨 UI/UX İyileştirmeleri

### Analytics Sayfası
- Modern KPI kartları
- İnteraktif grafikler (Chart.js)
- Responsive tasarım
- Gerçek zamanlı veri

### Broadcast Sayfası
- WhatsApp benzeri önizleme
- Hedef kitle seçimi
- Karakter sayacı
- Gönderim durumu takibi

### Contacts Sayfası
- Gelişmiş tablo görünümü
- Toplu seçim ve işlemler
- Sütun görünürlük ayarları
- Etiket filtreleme
- Inline düzenleme

### Settings Sayfası
- Tab bazlı navigasyon
- Workspace ayarları
- Team yönetimi
- **Mesaj şablonları** (YENİ!)
- Hızlı yanıtlar
- Profil yönetimi

---

## 🚀 Kullanım Senaryoları

### Senaryo 1: Kampanya Gönderimi

1. `/settings` > Mesaj Şablonları > Yeni şablon oluştur
2. Şablon içeriğini hazırla (değişkenlerle)
3. `/broadcast` sayfasına git
4. Hedef kitle seç (VIP müşteriler)
5. Şablon içeriğini kullan
6. Gönder

### Senaryo 2: Müşteri Segmentasyonu

1. `/contacts` sayfasına git
2. Yeni müşteri ekle (etiketlerle)
3. Etiket filtresini kullan
4. Segmente özel işlemler yap

### Senaryo 3: Performans Takibi

1. `/analytics` sayfasına git
2. KPI'ları incele
3. Temsilci performansını kontrol et
4. Trend grafiklerini analiz et

---

## 🔐 Güvenlik

- Session bazlı authentication
- Workspace izolasyonu (multi-tenant)
- Rate limiting (login endpoint)
- CORS yapılandırması
- SQL injection koruması (ORM)
- XSS koruması (frontend escaping)

---

## 📈 Performans

- SSE ile gerçek zamanlı güncellemeler
- Frontend cache (conversation cache)
- Debounced search (500ms)
- Lazy loading
- Optimized queries (eager loading)

---

## 🐛 Bilinen Sınırlamalar

1. **Broadcast:** Meta rate limit kurallarına tabidir
2. **SSE:** Tek worker ortamında çalışır (production için Redis önerilir)
3. **Templates:** Meta onaylı şablonlar için ayrı süreç gerekir
4. **Analytics:** Büyük veri setlerinde performans optimizasyonu gerekebilir

---

## 🔮 Gelecek Özellikler

- [ ] Chatbot / Otomatik yanıt
- [ ] Gelişmiş SLA takibi
- [ ] Export/Import (CSV, Excel)
- [ ] REST API (external integrations)
- [ ] Webhook yönetimi
- [ ] Custom dashboard widgets
- [ ] A/B testing (broadcast)
- [ ] Scheduled messages

---

## 📞 Destek

Sorularınız için:
- GitHub Issues
- Dokümantasyon: README.md
- Test: test_features.py
