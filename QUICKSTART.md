# WhatsApp CRM - Hızlı Başlangıç Rehberi

## 🚀 5 Dakikada Kurulum

### 1. Gereksinimler

```bash
# Python 3.8+ yüklü olmalı
python --version

# PostgreSQL veya SQLite (development için)
```

### 2. Projeyi Klonlayın

```bash
git clone <repository-url>
cd whatsapp-crm
```

### 3. Sanal Ortam Oluşturun

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 4. Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

### 5. Environment Dosyasını Oluşturun

```bash
# .env.example dosyasını kopyalayın
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac
```

`.env` dosyasını düzenleyin:

```env
# Database (SQLite - Development)
DATABASE_URL=sqlite:///instance/whatsapp_crm.db

# Flask
SECRET_KEY=your-secret-key-here-change-this
DEBUG=True

# WhatsApp API (Opsiyonel - sonra ayarlanabilir)
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WEBHOOK_VERIFY_TOKEN=your-random-secure-token
```

### 6. Veritabanını Oluşturun

```bash
# Tabloları oluştur
python app.py
# Ctrl+C ile durdurun

# Örnek verileri yükle
python seed_data.py
```

### 7. Uygulamayı Başlatın

```bash
python app.py
```

Tarayıcıda açın: `http://localhost:5000`

### 8. Giriş Yapın

**Admin Hesabı:**
- E-posta: `admin@example.com`
- Şifre: `admin123`

**Agent Hesabı:**
- E-posta: `agent@example.com`
- Şifre: `agent123`

---

## 🎯 İlk Adımlar

### 1. Workspace Ayarları

1. Sol menüden **Ayarlar** (⚙️) tıklayın
2. **Çalışma Alanı** sekmesinde:
   - Şirket adını girin
   - WhatsApp Phone Number ID'yi girin (Meta Dashboard'dan)
   - Access Token'ı girin
   - **Kaydet**

### 2. Takım Üyesi Ekleyin

1. **Ayarlar** > **Takım Üyeleri**
2. **Yeni Üye Ekle** butonuna tıklayın
3. Bilgileri doldurun
4. Rol seçin (Admin/Agent)
5. **Üye Oluştur**

### 3. Mesaj Şablonu Oluşturun

1. **Ayarlar** > **Mesaj Şablonları**
2. **Yeni Şablon** butonuna tıklayın
3. Şablon adı ve içeriği girin
4. Kategori seçin
5. **Şablonu Kaydet**

### 4. Müşteri Ekleyin

1. Sol menüden **Kişiler** (📖) tıklayın
2. **Yeni Kişi** butonuna tıklayın
3. Telefon numarası girin (zorunlu)
4. Diğer bilgileri doldurun
5. Etiketler ekleyin (VIP, Potansiyel, vb.)
6. **Kişiyi Kaydet**

### 5. Broadcast Gönderin

1. Sol menüden **Toplu Mesaj** (📢) tıklayın
2. Hedef kitle seçin:
   - Tüm Kişiler
   - Etikete Göre
3. Mesaj içeriğini yazın
4. Önizlemeyi kontrol edin
5. **Gönderimi Başlat**

### 6. Analytics İnceleyin

1. Sol menüden **Raporlar** (📊) tıklayın
2. KPI kartlarını inceleyin
3. Trend grafiklerini analiz edin
4. Temsilci performansını kontrol edin

---

## 🔧 WhatsApp API Kurulumu

### Meta Developer Console

1. [Meta for Developers](https://developers.facebook.com/) adresine gidin
2. Yeni uygulama oluşturun (Business type)
3. WhatsApp Business API'yi ekleyin

### Webhook Yapılandırması

1. WhatsApp > Configuration bölümüne gidin
2. Webhook URL'ini ayarlayın:
   ```
   https://your-domain.com/webhook
   ```
3. Verify Token'ı `.env` dosyasındaki `WEBHOOK_VERIFY_TOKEN` ile eşleştirin
4. `messages` event'ine subscribe olun

### Access Token

1. WhatsApp > API Setup bölümünden:
   - **Phone Number ID**'yi kopyalayın
   - **Temporary Access Token**'ı kopyalayın
2. Ayarlar sayfasından yapılandırın

### Test Numarası

1. Meta Dashboard'da test numarası ekleyin
2. Doğrulama kodunu girin
3. Test mesajı gönderin

---

## 🧪 Test

### Özellikleri Test Edin

```bash
# Sunucu çalışırken başka bir terminalde:
python test_features.py
```

Test edilen özellikler:
- ✓ Analytics API
- ✓ Message Templates
- ✓ Broadcast
- ✓ Contacts & Segmentation
- ✓ Workspace Settings
- ✓ Team Management

### Manuel Test

1. **Mesaj Gönderme:**
   - Ana sayfada bir konuşma seçin
   - Mesaj yazın ve gönderin

2. **Hızlı Yanıt:**
   - Mesaj kutusuna `/` yazın
   - Hızlı yanıt seçin

3. **Medya Gönderme:**
   - Ataş (📎) ikonuna tıklayın
   - Dosya seçin
   - Gönder

4. **Etiketleme:**
   - Konuşma detayında etiket seçin
   - Değişiklik otomatik kaydedilir

---

## 📊 Demo Veri Oluşturma

Daha fazla test verisi için:

```bash
# Sunucu çalışırken
curl -X POST http://localhost:5000/api/debug/populate \
  -H "Content-Type: application/json" \
  -b cookies.txt
```

Veya tarayıcı console'dan:

```javascript
fetch('/api/debug/populate', { method: 'POST' })
  .then(r => r.json())
  .then(console.log);
```

---

## 🐛 Sorun Giderme

### Veritabanı Hatası

```bash
# Veritabanını sıfırla
rm instance/whatsapp_crm.db
python app.py
python seed_data.py
```

### Port Zaten Kullanımda

```bash
# Farklı port kullan
PORT=5001 python app.py
```

### WhatsApp API Hatası

1. Access Token'ın geçerli olduğunu kontrol edin
2. Phone Number ID'nin doğru olduğunu kontrol edin
3. Meta Developer Console'da API çağrılarını inceleyin

### Webhook Çalışmıyor

1. HTTPS gereklidir (production için)
2. Verify token'ın eşleştiğini kontrol edin
3. Meta Console'da webhook subscription'ı kontrol edin

### Migration Gerekli

```bash
# Yeni tablolar ekle
python migrate_add_templates.py
```

---

## 📚 Daha Fazla Bilgi

- **Özellikler:** [FEATURES.md](FEATURES.md)
- **Ana Dokümantasyon:** [README.md](README.md)
- **API Referansı:** Kod içi yorumlar

---

## 🎓 Öğrenme Kaynakları

### WhatsApp Business API
- [Meta WhatsApp Docs](https://developers.facebook.com/docs/whatsapp)
- [Cloud API Quickstart](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started)

### Flask
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)

### Frontend
- [Tailwind CSS](https://tailwindcss.com/docs)
- [Chart.js](https://www.chartjs.org/docs/)

---

## 💡 İpuçları

1. **Development:** SQLite kullanın (kolay kurulum)
2. **Production:** PostgreSQL kullanın (daha performanslı)
3. **Webhook Test:** ngrok kullanın (local development için)
4. **Backup:** Düzenli veritabanı yedekleri alın
5. **Logs:** `server_logs.txt` dosyasını kontrol edin

---

## 🚀 Production Deployment

### Heroku

```bash
# Heroku CLI yükleyin
heroku create your-app-name
heroku addons:create heroku-postgresql:hobby-dev
git push heroku main
heroku run python seed_data.py
```

### Docker

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

### Environment Variables

Production'da mutlaka ayarlayın:
- `SECRET_KEY` (güçlü, rastgele)
- `DATABASE_URL` (PostgreSQL)
- `WHATSAPP_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WEBHOOK_VERIFY_TOKEN`

---

## 📞 Destek

Sorun mu yaşıyorsunuz?

1. [FEATURES.md](FEATURES.md) dosyasını kontrol edin
2. [README.md](README.md) dosyasını okuyun
3. Test scriptini çalıştırın: `python test_features.py`
4. GitHub Issues'da sorun bildirin

---

## ✅ Checklist

Kurulum tamamlandı mı?

- [ ] Python ve pip yüklü
- [ ] Sanal ortam oluşturuldu
- [ ] Bağımlılıklar yüklendi
- [ ] .env dosyası yapılandırıldı
- [ ] Veritabanı oluşturuldu
- [ ] Seed data yüklendi
- [ ] Uygulama başlatıldı
- [ ] Giriş yapıldı
- [ ] Workspace ayarları yapıldı
- [ ] Test edildi

Hepsi tamamsa, hazırsınız! 🎉
