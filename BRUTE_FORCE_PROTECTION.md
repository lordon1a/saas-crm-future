# Brute-Force Protection Implementation

## Özet

Flask CRM projesine brute-force ve rate limiting koruması eklendi.

## Yapılan Değişiklikler

### 1. LoginAttempt Modeli (models_crm.py)
- Yeni `login_attempts` tablosu eklendi
- Her login denemesi (başarılı/başarısız) kaydediliyor
- Email, IP, timestamp, success durumu ve user agent bilgisi saklanıyor
- Performance için 7 adet index eklendi

### 2. Brute-Force Kontrol Fonksiyonları (utils/permissions.py)

#### `check_login_attempts(email, ip_address)`
Login denemesinin izin verilip verilmeyeceğini kontrol eder.

**Güvenlik Kuralları:**
- Email bazlı: 15 dakikada maksimum 5 başarısız deneme
- IP bazlı: 15 dakikada maksimum 20 başarısız deneme (distributed attack koruması)
- Lockout süresi: Son başarısız denemeden itibaren 15 dakika

**Dönüş Değeri:**
```python
(allowed: bool, wait_minutes: int, reason: str)
```

#### `record_login_attempt(email, ip_address, success, user_agent)`
Her login denemesini veritabanına kaydeder.

### 3. Login Endpoint Güncellemesi (routes/auth.py)

**Eklenen Özellikler:**
- Login öncesi `check_login_attempts()` kontrolü
- Başarısız denemede 429 (Too Many Requests) response
- Her denemede (başarılı/başarısız) `record_login_attempt()` çağrısı
- Kullanıcıya kaç dakika beklemesi gerektiği bilgisi

**Response Örneği (Blocked):**
```json
{
  "error": "Çok fazla başarısız giriş denemesi. 12 dakika sonra tekrar deneyin.",
  "wait_minutes": 12,
  "locked_out": true
}
```

### 4. Migration Dosyası
- `migrations/add_login_attempts_table.py` oluşturuldu
- `app.py` içindeki `run_migrations()` fonksiyonu güncellendi
- Render Free Tier'da otomatik çalışacak şekilde yapılandırıldı

## Güvenlik Özellikleri

### Email-Based Protection
- Aynı email ile 15 dakikada 5'ten fazla başarısız deneme engellenir
- Hesap güvenliğini korur

### IP-Based Protection
- Aynı IP'den 15 dakikada 20'den fazla başarısız deneme engellenir
- Distributed brute-force saldırılarını önler
- Birden fazla hesaba saldırıyı engeller

### Lockout Mekanizması
- Son başarısız denemeden itibaren 15 dakika bekleme
- Kullanıcıya kalan süre bilgisi gösterilir
- Otomatik olarak süresi dolar

### Audit Trail
- Tüm login denemeleri kaydedilir
- IP adresi ve user agent bilgisi saklanır
- Güvenlik analizi için kullanılabilir

## Kullanım

### Login Flow
1. Kullanıcı email/password gönderir
2. `check_login_attempts()` kontrol edilir
3. Eğer limit aşılmışsa → 429 response + bekleme süresi
4. Eğer limit aşılmamışsa → normal auth flow
5. Sonuç (başarılı/başarısız) `record_login_attempt()` ile kaydedilir

### Monitoring
```python
# Son 24 saatteki başarısız denemeleri görüntüle
from models_crm import LoginAttempt
from datetime import datetime, timedelta

failed_attempts = LoginAttempt.query.filter(
    LoginAttempt.success == False,
    LoginAttempt.attempted_at >= datetime.utcnow() - timedelta(hours=24)
).all()
```

### Suspicious Activity Detection
```python
# Belirli bir IP'den çok sayıda farklı email denemesi
from sqlalchemy import func

suspicious_ips = db.session.query(
    LoginAttempt.ip_address,
    func.count(func.distinct(LoginAttempt.email)).label('unique_emails')
).filter(
    LoginAttempt.success == False,
    LoginAttempt.attempted_at >= datetime.utcnow() - timedelta(hours=1)
).group_by(LoginAttempt.ip_address).having(
    func.count(func.distinct(LoginAttempt.email)) > 10
).all()
```

## Testing

### Test Başarısız Login
```bash
# 5 kez yanlış şifre dene
for i in {1..5}; do
  curl -X POST http://localhost:5000/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}'
done

# 6. denemede 429 almalısın
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"wrong"}'
```

### Test IP-Based Blocking
```bash
# Farklı emaillerle 20+ deneme yap
# 21. denemede IP bazlı block almalısın
```

## Production Deployment

### Render'da Otomatik Migration
- `app.py` startup'ta `run_migrations()` çalışır
- `login_attempts` tablosu otomatik oluşturulur
- Index'ler otomatik eklenir

### Database Cleanup (Opsiyonel)
Eski kayıtları temizlemek için:
```python
# 30 günden eski kayıtları sil
from datetime import datetime, timedelta
from models_crm import LoginAttempt

old_date = datetime.utcnow() - timedelta(days=30)
LoginAttempt.query.filter(
    LoginAttempt.attempted_at < old_date
).delete()
db.session.commit()
```

## Performans

### Index Stratejisi
- `email + attempted_at`: Email bazlı sorgular için
- `ip_address + attempted_at`: IP bazlı sorgular için
- `success + attempted_at`: Başarısız deneme sorguları için

### Query Optimization
- 15 dakikalık time window ile sınırlı sorgular
- Index'ler sayesinde hızlı lookup
- Minimal overhead

## Güvenlik Notları

⚠️ **Önemli:**
- Bu koruma temel brute-force saldırılarını engeller
- Gelişmiş saldırılar için ek önlemler gerekebilir:
  - CAPTCHA (reCAPTCHA v3)
  - 2FA (Two-Factor Authentication) - zaten mevcut
  - IP whitelist/blacklist
  - Geolocation-based blocking
  - Device fingerprinting

## İlgili Dosyalar

- `models_crm.py` - LoginAttempt modeli
- `utils/permissions.py` - Brute-force kontrol fonksiyonları
- `routes/auth.py` - Login endpoint güncellemesi
- `migrations/add_login_attempts_table.py` - Migration script
- `app.py` - run_migrations() güncelleme

## Changelog

**2026-03-22:**
- ✅ LoginAttempt modeli eklendi
- ✅ check_login_attempts() ve record_login_attempt() fonksiyonları eklendi
- ✅ Login endpoint'i güncellendi
- ✅ Migration dosyası oluşturuldu
- ✅ app.py run_migrations() güncellendi
- ✅ Syntax kontrolü yapıldı
- ✅ Test edildi (local SQLite)
