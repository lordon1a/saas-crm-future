# Auto-Enrichment Engine — Kurulum Tamamlandı ✅

## Özet
WhatsApp, Telegram ve e-posta kanallarından gelen mesajları dinleyen, telefon numarası, şirket adı ve e-posta adresi çıkarıp contact kartını sessizce güncelleyen arka plan servisi.

## Yapılan Değişiklikler

### 1. Model (models_crm.py)
- ✅ `EnrichmentLog` modeli eklendi
- Tüm güncellemeleri loglar (old_value, new_value, confidence, source)

### 2. Migration (migrations/add_enrichment_logs.py)
- ✅ `enrichment_logs` tablosu oluşturuldu
- ✅ `app.py` → `run_migrations()` fonksiyonuna eklendi

### 3. Servisler
- ✅ `services/enrichment.py` — Ana enrichment engine
  - Regex parser (telefon, e-posta, şirket)
  - LLM fallback (şirket adı için)
  - Contact güncelleme + log kaydetme
  
- ✅ `services/enrichment_llm.py` — LLM entity extraction
  - AI ile daha karmaşık şirket adlarını çıkarır
  - JSON formatında döndürür

### 4. Kanal Entegrasyonları
- ✅ **WhatsApp** (`services/webhook_handler.py`)
  - Mesaj kaydedildikten sonra arka planda enrich eder
  
- ✅ **Telegram** (`services/telegram_service.py`)
  - Activity kaydından sonra enrich eder
  
- ✅ **E-posta** (`services/gmail_sync_service.py`)
  - E-posta sync'ten sonra enrich eder

### 5. API Endpoint
- ✅ `GET /api/ai/enrichment-log/<contact_id>`
  - Contact için son 20 enrichment kaydını döndürür
  - Auth required + AI Assistant app gerekli

### 6. UI (templates/contact_detail.html)
- ✅ Sidebar'a "Otomatik Güncelleme" section'ı eklendi
- İlk 5 log kaydını gösterir
- Kaynak (WhatsApp/Telegram/Email) ikonları
- Güven skoru (confidence) gösterir

## Nasıl Çalışır?

1. **Mesaj gelir** (WhatsApp/Telegram/Email)
2. **Regex parser** çalışır → telefon, e-posta, şirket adı arar
3. **Şirket bulunamazsa** → LLM'e gönderilir (AI Settings gerekli)
4. **Confidence > 0.7** ise → Contact güncellenir
5. **EnrichmentLog** kaydedilir → UI'da görünür

## Test Etme

### 1. Migration'ı çalıştır (Render'da otomatik)
```bash
python migrations/add_enrichment_logs.py
```

### 2. Manuel test
```bash
python test_enrichment.py
```
Test script'te `contact_id` ve `workspace_id` değerlerini düzenle.

### 3. Gerçek test
- WhatsApp'tan mesaj gönder: "Merhaba, ben Ahmet. Tekno A.Ş'den arıyorum. 0532 111 22 33"
- Contact kartını aç → "Otomatik Güncelleme" section'ını kontrol et
- Telefon ve şirket güncellenmiş olmalı

## Confidence Skorları

| Kaynak | Telefon | E-posta | Şirket (Regex) | Şirket (LLM) |
|--------|---------|---------|----------------|--------------|
| Skor   | 0.95    | 0.99    | 0.75           | 0.80         |

Minimum threshold: **0.7** (daha düşük skorlar güncelleme yapmaz)

## Güvenlik
- ✅ Multi-tenant izolasyon (workspace_id)
- ✅ Thread-safe (daemon thread kullanır)
- ✅ Rollback on error
- ✅ Raw message 500 karakter ile sınırlı (privacy)

## Performans
- Arka planda çalışır (blocking yapmaz)
- Regex önce çalışır (hızlı)
- LLM sadece gerekirse çağrılır (yavaş ama akıllı)
- Render Free Tier uyumlu (hafif işlem)

## Gelecek İyileştirmeler
- [ ] Duplicate detection (aynı değer tekrar yazılmasın)
- [ ] Confidence threshold ayarlanabilir olsun
- [ ] Enrichment onay mekanizması (manuel approval)
- [ ] Bulk enrichment (tüm contact'ları toplu işle)
- [ ] Enrichment analytics (kaç güncelleme yapıldı?)
