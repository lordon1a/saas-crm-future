# WhatsApp CRM MVP (v1.0)

Flask tabanlı minimal WhatsApp CRM sistemi. Meta WhatsApp Cloud API ile entegre çalışır.

## Özellikler

✅ Gelen WhatsApp mesajlarını webhook ile alma  
✅ Müşterilere mesaj gönderme (metin + medya)  
✅ Sohbet geçmişi ve müşteri yönetimi  
✅ Sohbet etiketleme (yeni_siparis, kargo_sorunu, odeme_bekliyor)  
✅ Hazır yanıt şablonları  
✅ Gerçek zamanlı güncelleme (SSE + polling)  
✅ Multi-tenant (çoklu işletme) desteği  
✅ Kullanıcı yetkilendirme sistemi (admin/agent)  
✅ Analytics & Raporlama dashboard'u  
✅ Broadcast (Toplu mesaj gönderimi)  
✅ Mesaj şablonları yönetimi  
✅ Müşteri segmentasyonu (etiketler)  
✅ Medya gönderimi (görsel, belge, ses, video)  
✅ Temsilci atama ve takip  

## Kurulum

### 1. Gereksinimler

- Python 3.8+
- PostgreSQL 12+
- Meta WhatsApp Business Account

### 2. Veritabanı Oluşturma

```bash
# PostgreSQL'de yeni veritabanı oluşturun
createdb whatsapp_crm

# veya psql ile:
psql -U postgres
CREATE DATABASE whatsapp_crm;
\q
```

### 3. Proje Kurulumu

```bash
# Bağımlılıkları yükleyin
pip install -r requirements.txt

# .env dosyası oluşturun
copy .env.example .env

# .env dosyasını düzenleyin ve gerekli değerleri doldurun
```

### 4. Environment Variables (.env)

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/whatsapp_crm

# Meta WhatsApp Cloud API
WHATSAPP_TOKEN=your_meta_access_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here

# Webhook
WEBHOOK_VERIFY_TOKEN=your_random_secure_token_here

# Flask
SECRET_KEY=your_secret_key_here
```

**Önemli:** 
- `WEBHOOK_VERIFY_TOKEN`: Rastgele güvenli bir string (min 32 karakter)
- `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"` ile oluşturabilirsiniz

### 5. Veritabanı Tablolarını Oluşturma

```bash
# Uygulamayı bir kez çalıştırın (tablolar otomatik oluşturulur)
python app.py

# Ctrl+C ile durdurun
```

### 6. Seed Data (İlk Veriler)

```bash
# Admin kullanıcı ve hazır yanıtları oluşturun
python seed_data.py
```

**Varsayılan Kullanıcılar:**
- Admin: `admin@example.com` / `admin123`
- Agent: `agent@example.com` / `agent123`

### 7. Uygulamayı Başlatma

```bash
python app.py
```

Tarayıcıda `http://localhost:5000` adresini açın.

## Meta WhatsApp Cloud API Kurulumu

### 1. Meta Developer Console

1. [Meta for Developers](https://developers.facebook.com/) adresine gidin
2. Yeni uygulama oluşturun (Business type)
3. WhatsApp Business API'yi ekleyin

### 2. Webhook Konfigürasyonu

1. WhatsApp > Configuration bölümüne gidin
2. Webhook URL'ini ayarlayın: `https://your-domain.com/webhook`
3. Verify Token'ı `.env` dosyasındaki `WEBHOOK_VERIFY_TOKEN` ile eşleştirin
4. `messages` event'ine subscribe olun

### 3. Access Token

1. WhatsApp > API Setup bölümünden Temporary Access Token'ı kopyalayın
2. `.env` dosyasındaki `WHATSAPP_TOKEN` değerine yapıştırın
3. Phone Number ID'yi kopyalayın ve `WHATSAPP_PHONE_NUMBER_ID` değerine yapıştırın

### 4. Production için

- Temporary token yerine Permanent Access Token oluşturun
- Webhook URL'inizi HTTPS ile yayınlayın (ngrok, Heroku, vb.)
- Business verification yapın

## Kullanım

### Webhook Test

```bash
# GET request (verification)
curl "http://localhost:5000/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test123"

# Başarılı ise "test123" döner
```

### API Endpoints

```bash
# Sohbet listesi
GET /api/conversations

# Mesaj geçmişi
GET /api/conversations/1/messages

# Mesaj gönder
POST /api/messages/send
{
  "conversation_id": 1,
  "message_body": "Merhaba!"
}

# Etiket güncelle
PUT /api/conversations/1/tag
{
  "tag": "yeni_siparis"
}

# Hazır yanıtlar
GET /api/quick-replies
```

## Proje Yapısı

```
whatsapp-crm-mvp/
├── app.py                 # Ana uygulama
├── config.py              # Konfigürasyon
├── models.py              # Veritabanı modelleri
├── seed_data.py           # İlk veri oluşturma
├── requirements.txt       # Python bağımlılıkları
├── .env.example           # Environment variables şablonu
├── routes/
│   ├── __init__.py
│   ├── webhook.py         # Webhook endpoints
│   └── api.py             # Internal API endpoints
├── services/
│   ├── __init__.py
│   ├── auth_manager.py
│   ├── customer_manager.py
│   ├── conversation_manager.py
│   ├── message_manager.py
│   ├── meta_api_client.py
│   ├── quick_reply_manager.py
│   └── webhook_handler.py
├── static/
│   ├── style.css          # CSS stilleri
│   └── app.js             # Frontend JavaScript
└── templates/
    └── index.html         # Ana sayfa
```

## MVP Sınırlamaları

Bu versiyonda **dahil değil**:

❌ Chatbot / Otomatik yanıt (gelecek versiyonda)  
❌ Gelişmiş SLA takibi  
❌ Export/import özellikleri  
❌ Entegrasyon API'leri (REST API)  

Yukarıdaki özellikler gelecek versiyonlarda eklenecektir.

## Sorun Giderme

### Veritabanı Bağlantı Hatası

```bash
# PostgreSQL'in çalıştığından emin olun
pg_ctl status

# Veritabanının var olduğunu kontrol edin
psql -l | grep whatsapp_crm
```

### Meta API Hataları

- Access Token'ın geçerli olduğundan emin olun
- Phone Number ID'nin doğru olduğunu kontrol edin
- Meta Developer Console'da API çağrılarını inceleyin

### Webhook Çalışmıyor

- Webhook URL'inin HTTPS olması gerekir (production için)
- Verify token'ın eşleştiğinden emin olun
- Meta Console'da webhook subscription'ı kontrol edin

## Geliştirme

```bash
# Development mode
python app.py

# Seed data'yı yeniden oluştur
python seed_data.py
```

## Lisans

MIT
