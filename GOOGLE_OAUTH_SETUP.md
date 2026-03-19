# Google OAuth Kurulum Rehberi

Bu rehber, WhatsApp CRM'e Google Workspace entegrasyonu (Gmail, Calendar, Drive) eklemek için gerekli OAuth credentials'ı nasıl alacağınızı adım adım anlatır.

## 📋 Gereksinimler

- Google hesabı (Gmail)
- Google Cloud Console erişimi
- Render.com'da deploy edilmiş uygulama

## 🚀 Adım 1: Google Cloud Console'a Giriş

1. **Google Cloud Console'a git:**
   - https://console.cloud.google.com/

2. **Yeni proje oluştur:**
   - Sol üstteki proje seçiciye tıkla
   - "New Project" butonuna tıkla
   - Proje adı: `WhatsApp CRM` (veya istediğin bir isim)
   - "Create" butonuna tıkla

## 🔑 Adım 2: OAuth Consent Screen Yapılandırması

1. **OAuth consent screen'e git:**
   - Sol menüden "APIs & Services" > "OAuth consent screen"

2. **User Type seçimi:**
   - "External" seçeneğini işaretle (herkes kullanabilir)
   - "Create" butonuna tıkla

3. **App information:**
   - App name: `WhatsApp CRM`
   - User support email: Kendi email adresin
   - App logo: (opsiyonel)
   - Application home page: `https://whatsapp-crm-saas.onrender.com`
   - Application privacy policy: `https://whatsapp-crm-saas.onrender.com` (şimdilik)
   - Application terms of service: `https://whatsapp-crm-saas.onrender.com` (şimdilik)
   - Developer contact email: Kendi email adresin
   - "Save and Continue" butonuna tıkla

4. **Scopes (İzinler):**
   - "Add or Remove Scopes" butonuna tıkla
   - Şu scope'ları ekle:
     - `openid`
     - `email`
     - `profile`
     - `https://www.googleapis.com/auth/gmail.readonly` (Gmail okuma)
     - `https://www.googleapis.com/auth/calendar.readonly` (Calendar okuma)
     - `https://www.googleapis.com/auth/drive.readonly` (Drive okuma)
   - "Update" butonuna tıkla
   - "Save and Continue" butonuna tıkla

5. **Test users:**
   - "Add Users" butonuna tıkla
   - Kendi Gmail adresini ekle
   - "Save and Continue" butonuna tıkla

6. **Summary:**
   - "Back to Dashboard" butonuna tıkla

## 🔐 Adım 3: OAuth Credentials Oluşturma

1. **Credentials sayfasına git:**
   - Sol menüden "APIs & Services" > "Credentials"

2. **OAuth Client ID oluştur:**
   - "Create Credentials" butonuna tıkla
   - "OAuth client ID" seçeneğini seç

3. **Application type:**
   - "Web application" seçeneğini işaretle

4. **Name:**
   - `WhatsApp CRM Web Client`

5. **Authorized JavaScript origins:**
   - "Add URI" butonuna tıkla
   - `https://whatsapp-crm-saas.onrender.com` ekle

6. **Authorized redirect URIs:**
   - "Add URI" butonuna tıkla
   - `https://whatsapp-crm-saas.onrender.com/integrations/google/callback` ekle
   - ⚠️ **ÖNEMLİ:** URL'nin sonunda `/` olmamalı!

7. **Create:**
   - "Create" butonuna tıkla
   - Açılan popup'ta **Client ID** ve **Client Secret** görünecek
   - Bu bilgileri kopyala ve güvenli bir yere kaydet

## 📝 Adım 4: Gmail API'yi Etkinleştir

1. **API Library'ye git:**
   - Sol menüden "APIs & Services" > "Library"

2. **Gmail API'yi ara ve etkinleştir:**
   - Arama kutusuna "Gmail API" yaz
   - "Gmail API" sonucuna tıkla
   - "Enable" butonuna tıkla

3. **Google Calendar API'yi ara ve etkinleştir:**
   - Arama kutusuna "Google Calendar API" yaz
   - "Google Calendar API" sonucuna tıkla
   - "Enable" butonuna tıkla

4. **Google Drive API'yi ara ve etkinleştir:**
   - Arama kutusuna "Google Drive API" yaz
   - "Google Drive API" sonucuna tıkla
   - "Enable" butonuna tıkla

## 🌐 Adım 5: Render.com'da Environment Variables Ayarlama

1. **Render Dashboard'a git:**
   - https://dashboard.render.com/

2. **WhatsApp CRM servisini seç**

3. **Environment sekmesine git**

4. **Şu environment variable'ları ekle:**

   ```
   GOOGLE_CLIENT_ID=<Client ID'yi buraya yapıştır>
   GOOGLE_CLIENT_SECRET=<Client Secret'i buraya yapıştır>
   GOOGLE_REDIRECT_URI=https://whatsapp-crm-saas.onrender.com/integrations/google/callback
   ```

   **Örnek:**
   ```
   GOOGLE_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-AbCdEfGhIjKlMnOpQrStUvWxYz
   GOOGLE_REDIRECT_URI=https://whatsapp-crm-saas.onrender.com/integrations/google/callback
   ```

5. **Save Changes butonuna tıkla**

6. **Uygulama otomatik olarak yeniden deploy edilecek (2-3 dakika)**

## ✅ Adım 6: Test Etme

1. **Deploy tamamlandıktan sonra:**
   - https://whatsapp-crm-saas.onrender.com/settings adresine git

2. **Google Workspace tab'ına tıkla**

3. **"Google'a Bağlan" butonuna tıkla**

4. **Google login sayfası açılacak:**
   - Gmail hesabınla giriş yap
   - İzinleri onayla
   - Callback URL'e yönlendirileceksin

5. **Başarılı bağlantı:**
   - "Bağlantı aktif" mesajını göreceksin
   - Gmail ve Calendar sync butonları aktif olacak
   - Email tracking çalışmaya başlayacak

## 🔧 Sorun Giderme

### "Google OAuth is not configured" hatası
- Render'da environment variable'ların doğru girildiğinden emin ol
- Deploy'un tamamlandığından emin ol
- Sayfayı yenile (Ctrl+F5)

### "Redirect URI mismatch" hatası
- Google Cloud Console'da Authorized redirect URIs'in tam olarak şu olduğundan emin ol:
  ```
  https://whatsapp-crm-saas.onrender.com/integrations/google/callback
  ```
- URL'nin sonunda `/` olmamalı
- `http` değil `https` olmalı

### "Access blocked: This app's request is invalid" hatası
- OAuth consent screen'de "External" seçildiğinden emin ol
- Test users'a kendi email adresini eklediğinden emin ol
- Gmail, Calendar ve Drive API'lerinin enabled olduğundan emin ol

### "Invalid grant" hatası
- Token'lar expire olmuş olabilir
- Settings'den "Bağlantıyı Kes" butonuna tıkla
- Tekrar "Google'a Bağlan" butonuna tıkla

## 📚 Ek Bilgiler

### Scope'lar Ne İşe Yarar?

- `openid, email, profile`: Kullanıcı bilgilerini almak için
- `gmail.readonly`: Gmail'deki emailları okumak için
- `calendar.readonly`: Google Calendar'daki etkinlikleri okumak için
- `drive.readonly`: Google Drive'daki dosyaları okumak için

### Production'a Geçiş

Şu anda "Testing" modundasın (sadece test users kullanabilir). Production'a geçmek için:

1. Google Cloud Console > OAuth consent screen
2. "Publish App" butonuna tıkla
3. Google'ın verification sürecini tamamla (1-2 hafta sürebilir)

Ama şimdilik test modunda kendi hesabınla kullanabilirsin!

## 🎉 Tamamlandı!

Artık Google Workspace entegrasyonu çalışıyor! Şu özellikleri kullanabilirsin:

- ✅ Gmail sync (emailları otomatik çek)
- ✅ Calendar sync (toplantıları otomatik çek)
- ✅ Drive file picker (dosyaları deal/task'lara ekle)
- ✅ Email tracking (email açılma/tıklama takibi)

Herhangi bir sorun yaşarsan, Render logs'larını kontrol et:
```
Render Dashboard > WhatsApp CRM > Logs
```
