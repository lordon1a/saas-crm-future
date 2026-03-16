# Google Drive Scope Hatası Düzeltildi

## Sorun
Google OAuth bağlantısı yapıldı ama Drive API çalışmıyor. Hata:
```
HttpError 403: Request had insufficient authentication scopes
Insufficient Permission: insufficientPermissions
```

## Neden?
OAuth bağlantısı yapılırken Drive scope'u (`https://www.googleapis.com/auth/drive.readonly`) istenmemiş. Sadece Gmail ve Calendar scope'ları vardı.

## Çözüm

### 1. Kod Değişiklikleri (✅ Yapıldı)

- `config.py`: Drive scope eklendi
- `.env.example`: Drive scope eklendi  
- `templates/settings.html`: Email tracking yükleme düzeltildi

### 2. Render Environment Variable Güncelleme (❌ Yapılacak)

Render Dashboard'da `GOOGLE_OAUTH_SCOPES` environment variable'ını güncelle:

**Eski değer:**
```
openid,email,profile,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/calendar.readonly
```

**Yeni değer:**
```
openid,email,profile,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly
```

### 3. Google'a Yeniden Bağlan (❌ Yapılacak)

Scope değiştiği için Google OAuth'u yeniden authorize etmen gerekiyor:

1. https://whatsapp-crm-saas.onrender.com/settings
2. Google Workspace tab
3. "Bağlantıyı Kes" butonuna tıkla
4. "Google'a Bağlan" butonuna tıkla
5. Google izin sayfasında **Drive izni de göreceksin**
6. İzinleri onayla

## Adımlar

### Adım 1: Kodu Deploy Et
```bash
git add config.py .env.example templates/settings.html GOOGLE_DRIVE_FIX.md
git commit -m "Fix: Add Google Drive scope for file picker"
git push origin main
```

### Adım 2: Render'da Environment Variable Güncelle

1. https://dashboard.render.com/ → WhatsApp CRM servisi
2. Environment sekmesi
3. `GOOGLE_OAUTH_SCOPES` variable'ını bul
4. Edit butonuna tıkla
5. Değeri şununla değiştir:
   ```
   openid,email,profile,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly
   ```
6. Save Changes

### Adım 3: Deploy Bitsin (3-5 dakika)

Render otomatik deploy yapacak.

### Adım 4: Google'a Yeniden Bağlan

1. https://whatsapp-crm-saas.onrender.com/settings
2. Google Workspace → "Bağlantıyı Kes"
3. "Google'a Bağlan"
4. İzinleri onayla (Drive izni de olacak)

### Adım 5: Test Et

Settings → Google Workspace → Google Drive Dosyaları bölümü çalışacak!

## Sonuç

Artık şunlar çalışacak:
- ✅ Gmail sync
- ✅ Calendar sync  
- ✅ Drive file picker (dosya listesi)
- ✅ Email tracking dashboard

## Not

Eğer `GOOGLE_OAUTH_SCOPES` environment variable'ı Render'da yoksa, kod otomatik olarak default değeri kullanacak (Drive scope dahil). Ama varsa, onu güncellemelisin.
