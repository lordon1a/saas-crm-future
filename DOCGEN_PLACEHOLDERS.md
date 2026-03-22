# DocGen Template Placeholder Reference

Bu doküman, DocGen modülünde kullanabileceğiniz tüm placeholder'ları listeler.

## Genel Placeholder'lar

### Tarih ve Kullanıcı
- `{{today}}` - Bugünün tarihi (YYYY-MM-DD formatında)
- `{{user.id}}` - Mevcut kullanıcının ID'si
- `{{user.name}}` - Mevcut kullanıcının adı
- `{{user.email}}` - Mevcut kullanıcının e-posta adresi
- `{{workspace.id}}` - Workspace ID'si
- `{{workspace.name}}` - Workspace adı (şirket adı)

---

## Deal (Fırsat) Placeholder'ları

### Temel Bilgiler
- `{{deal.id}}` - Deal ID
- `{{deal.name}}` - Deal adı
- `{{deal.status}}` - Deal durumu (open, won, lost)
- `{{deal.value}}` - Deal değeri (sayısal)
- `{{deal.value_formatted}}` - Deal değeri (formatlanmış: 1,234.56)
- `{{deal.currency}}` - Para birimi (TRY)

### Gelir Bilgileri
- `{{deal.revenue_type}}` - Gelir tipi (one_time, recurring)
- `{{deal.mrr}}` - Aylık yinelenen gelir
- `{{deal.arr}}` - Yıllık yinelenen gelir
- `{{deal.forecast_category}}` - Tahmin kategorisi (pipeline, best_case, commit)
- `{{deal.churn_risk}}` - Kayıp riski (low, medium, high)

### Tarihler
- `{{deal.expected_close_date}}` - Beklenen kapanış tarihi
- `{{deal.renewal_date}}` - Yenileme tarihi
- `{{deal.created_at}}` - Oluşturulma tarihi
- `{{deal.updated_at}}` - Güncellenme tarihi
- `{{deal.closed_at}}` - Kapanış tarihi
- `{{deal.stage_entered_at}}` - Mevcut aşamaya giriş tarihi

### Aşama ve Pipeline
- `{{deal.stage_name}}` - Aşama adı
- `{{deal.stage_probability}}` - Aşama olasılığı (0-100)
- `{{deal.stage_order}}` - Aşama sırası
- `{{deal.pipeline_name}}` - Pipeline adı
- `{{deal.days_in_stage}}` - Aşamada geçen gün sayısı
- `{{deal.is_rotting}}` - Çürüme durumu (True/False)
- `{{deal.weighted_value}}` - Ağırlıklı değer (value × probability)

### Diğer
- `{{deal.next_step}}` - Sonraki adım
- `{{deal.win_loss_reason}}` - Kazanma/kaybetme nedeni

---

## Contact (Kişi) Placeholder'ları

### Temel Bilgiler
- `{{contact.id}}` - Contact ID
- `{{contact.name}}` - Tam ad
- `{{contact.first_name}}` - Ad
- `{{contact.last_name}}` - Soyad
- `{{contact.email}}` - E-posta adresi
- `{{contact.phone}}` - Telefon numarası
- `{{contact.whatsapp_phone}}` - WhatsApp telefon numarası
- `{{contact.telegram_chat_id}}` - Telegram chat ID

### İş Bilgileri
- `{{contact.job_title}}` - İş unvanı
- `{{contact.role}}` - Rol (Decision Maker, Influencer, vb.)

### Lead Yönetimi
- `{{contact.lead_score}}` - Lead skoru (0-100)
- `{{contact.lead_source}}` - Lead kaynağı (web, referral, vb.)
- `{{contact.lifecycle_stage}}` - Yaşam döngüsü aşaması (lead, qualified_lead, customer, evangelist)
- `{{contact.is_starred}}` - Yıldızlı mı? (True/False)

### Tarihler
- `{{contact.created_at}}` - Oluşturulma tarihi
- `{{contact.updated_at}}` - Güncellenme tarihi
- `{{contact.qualified_at}}` - Nitelikli lead olma tarihi
- `{{contact.converted_at}}` - Müşteriye dönüşme tarihi
- `{{contact.last_activity_at}}` - Son aktivite tarihi

---

## Company (Şirket) Placeholder'ları

### Temel Bilgiler
- `{{company.id}}` - Company ID
- `{{company.name}}` - Şirket adı
- `{{company.industry}}` - Sektör
- `{{company.size}}` - Şirket büyüklüğü (1-10, 11-50, vb.)
- `{{company.website}}` - Web sitesi
- `{{company.phone}}` - Telefon numarası
- `{{company.address}}` - Adres

### Tarihler
- `{{company.created_at}}` - Oluşturulma tarihi
- `{{company.updated_at}}` - Güncellenme tarihi

---

## Quote (Teklif) Placeholder'ları

### Temel Bilgiler
- `{{quote.id}}` - Quote ID
- `{{quote.quote_number}}` - Teklif numarası
- `{{quote.status}}` - Durum (draft, sent, accepted, rejected, expired)
- `{{quote.currency}}` - Para birimi

### Finansal Bilgiler
- `{{quote.subtotal}}` - Ara toplam (sayısal)
- `{{quote.subtotal_formatted}}` - Ara toplam (formatlanmış)
- `{{quote.discount_total}}` - Toplam indirim (sayısal)
- `{{quote.discount_total_formatted}}` - Toplam indirim (formatlanmış)
- `{{quote.tax_total}}` - Toplam vergi (sayısal)
- `{{quote.tax_total_formatted}}` - Toplam vergi (formatlanmış)
- `{{quote.grand_total}}` - Genel toplam (sayısal)
- `{{quote.grand_total_formatted}}` - Genel toplam (formatlanmış)

### Diğer
- `{{quote.notes}}` - Notlar
- `{{quote.valid_until}}` - Geçerlilik tarihi
- `{{quote.created_at}}` - Oluşturulma tarihi
- `{{quote.updated_at}}` - Güncellenme tarihi

---

## Task (Görev) Placeholder'ları

### Temel Bilgiler
- `{{task.id}}` - Task ID
- `{{task.title}}` - Görev başlığı
- `{{task.description}}` - Görev açıklaması
- `{{task.status}}` - Durum (pending, in_progress, completed, cancelled)
- `{{task.priority}}` - Öncelik (low, medium, high, urgent)

### Tarihler
- `{{task.due_date}}` - Bitiş tarihi
- `{{task.completed_at}}` - Tamamlanma tarihi
- `{{task.created_at}}` - Oluşturulma tarihi
- `{{task.updated_at}}` - Güncellenme tarihi

---

## Product (Ürün) Placeholder'ları

### Temel Bilgiler
- `{{product.id}}` - Product ID
- `{{product.name}}` - Ürün adı
- `{{product.sku}}` - Stok kodu
- `{{product.description}}` - Ürün açıklaması
- `{{product.unit_price}}` - Birim fiyat (sayısal)
- `{{product.unit_price_formatted}}` - Birim fiyat (formatlanmış)
- `{{product.currency}}` - Para birimi
- `{{product.is_active}}` - Aktif mi? (True/False)

### Tarihler
- `{{product.created_at}}` - Oluşturulma tarihi
- `{{product.updated_at}}` - Güncellenme tarihi

---

## İlişkili Kayıtlar

DocGen otomatik olarak ilişkili kayıtları çeker:

- **Deal şablonunda**: Deal, Contact, Company bilgileri otomatik eklenir
- **Quote şablonunda**: Quote, Deal, Contact, Company bilgileri otomatik eklenir
- **Task şablonunda**: Task, Deal, Contact bilgileri otomatik eklenir
- **Contact şablonunda**: Contact, Company bilgileri otomatik eklenir

---

## Örnek Şablon

```
TEKLİF FORMU

Tarih: {{today}}
Teklif No: {{quote.quote_number}}

Sayın {{contact.name}},

{{company.name}} şirketi için hazırladığımız teklifimiz aşağıdaki gibidir:

Proje Adı: {{deal.name}}
Teklif Tutarı: {{deal.value_formatted}} {{deal.currency}}
Geçerlilik Süresi: {{quote.valid_until}}

Proje Detayları:
{{deal.next_step}}

İletişim Bilgileri:
Email: {{contact.email}}
Telefon: {{contact.phone}}
Şirket: {{company.name}}
Adres: {{company.address}}

Finansal Özet:
Ara Toplam: {{quote.subtotal_formatted}} {{quote.currency}}
İndirim: {{quote.discount_total_formatted}} {{quote.currency}}
Vergi: {{quote.tax_total_formatted}} {{quote.currency}}
Genel Toplam: {{quote.grand_total_formatted}} {{quote.currency}}

Saygılarımızla,
{{user.name}}
{{workspace.name}}
```

---

## Notlar

1. Tüm tarih alanları `YYYY-MM-DD` formatındadır
2. Formatlanmış para alanları (`_formatted`) virgül ve ondalık ayırıcı içerir
3. Boolean alanlar `True` veya `False` değeri döner
4. Boş alanlar boş string (`""`) olarak döner
5. İlişkili kayıtlar yoksa ilgili placeholder'lar boş olur
