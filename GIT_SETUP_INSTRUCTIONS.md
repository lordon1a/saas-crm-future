# Git Kurulum ve GitHub'a Yükleme Talimatları

## ⚠️ Git Kurulu Değil

Sisteminizde Git kurulu değil. Aşağıdaki adımları takip edin:

## Adım 1: Git Kurulumu

### Windows için:

1. **Git'i İndirin:**
   - https://git-scm.com/download/win adresine gidin
   - "64-bit Git for Windows Setup" linkine tıklayın
   - İndirilen .exe dosyasını çalıştırın

2. **Kurulum Sırasında:**
   - Tüm varsayılan ayarları kabul edin
   - "Git Bash" ve "Git from the command line" seçeneklerinin işaretli olduğundan emin olun

3. **Kurulum Sonrası:**
   - PowerShell veya Command Prompt'u **KAPATIN ve YENİDEN AÇIN**
   - Test edin: `git --version`

### Alternatif: GitHub Desktop (Daha Kolay)

Eğer komut satırı yerine görsel arayüz tercih ediyorsanız:

1. **GitHub Desktop İndirin:**
   - https://desktop.github.com/ adresine gidin
   - İndirin ve kurun

2. **GitHub Hesabınızla Giriş Yapın**

3. **Projeyi Ekleyin:**
   - File → Add Local Repository
   - Proje klasörünü seçin: `C:\Users\lordo\OneDrive\Masaüstü\whatsapp crm`
   - "Create a repository" seçeneğini seçin

4. **Commit ve Push:**
   - Sol altta commit mesajı yazın: "Initial commit: Ready for Render deployment"
   - "Commit to main" butonuna tıklayın
   - "Publish repository" butonuna tıklayın
   - "Private" seçeneğini işaretleyin
   - Repository adı: `whatsapp-crm-saas`

## Adım 2: Git Kurulduktan Sonra (Komut Satırı)

PowerShell'i **yeniden açtıktan sonra** şu komutları çalıştırın:

```powershell
# Proje klasörüne gidin
cd "C:\Users\lordo\OneDrive\Masaüstü\whatsapp crm"

# Git kullanıcı bilgilerinizi ayarlayın (ilk kez kullanıyorsanız)
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Git repository'yi başlatın
git init

# Tüm dosyaları ekleyin
git add .

# İlk commit'i yapın
git commit -m "Initial commit: Ready for Render deployment"
```

## Adım 3: GitHub'a Yükleme

### Seçenek A: GitHub CLI Varsa (Önerilen)

```powershell
# GitHub CLI kurulu mu kontrol edin
gh --version

# Kuruluysa, doğrudan repo oluşturun ve push edin
gh auth login
gh repo create whatsapp-crm-saas --private --source=. --remote=origin --push
```

### Seçenek B: GitHub CLI Yoksa (Manuel)

1. **GitHub.com'da Boş Repo Oluşturun:**
   - https://github.com/new adresine gidin
   - Repository name: `whatsapp-crm-saas`
   - Private seçeneğini işaretleyin
   - **"Add a README file" seçeneğini İŞARETLEMEYİN**
   - "Create repository" butonuna tıklayın

2. **Terminalde Şu Komutları Çalıştırın:**

   GitHub'da oluşturduğunuz repo sayfasında gösterilen komutları kullanın, veya:

   ```powershell
   git remote add origin https://github.com/KULLANICI_ADINIZ/whatsapp-crm-saas.git
   git branch -M main
   git push -u origin main
   ```

   **NOT:** `KULLANICI_ADINIZ` yerine kendi GitHub kullanıcı adınızı yazın!

## Adım 4: GitHub'a Push Sonrası Kontrol

1. GitHub repo sayfanızı yenileyin
2. Tüm dosyaların yüklendiğini kontrol edin
3. `.env` dosyasının **OLMAMASI** gerekir (güvenlik)
4. `Procfile`, `requirements.txt`, `runtime.txt` dosyalarının olduğunu doğrulayın

## Adım 5: Render.com'a Deploy

GitHub'a yükleme tamamlandıktan sonra:

1. **Render.com'a Gidin:**
   - https://render.com/ → Sign Up (GitHub ile giriş yapın)

2. **New Web Service:**
   - Dashboard → "New +" → "Web Service"
   - GitHub repository'nizi seçin: `whatsapp-crm-saas`

3. **Ayarları Yapın:**
   - Name: `whatsapp-crm-saas`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Instance Type: `Free`

4. **Environment Variables Ekleyin:**
   
   "Environment" sekmesine gidin ve şu değişkenleri ekleyin:

   ```
   FLASK_ENV=production
   FLASK_DEBUG=0
   SECRET_KEY=<generate-with-command-below>
   WHATSAPP_TOKEN=your_meta_token
   WHATSAPP_PHONE_NUMBER_ID=your_phone_id
   WEBHOOK_VERIFY_TOKEN=your_webhook_token
   CORS_ORIGINS=https://your-app-name.onrender.com
   ```

   **SECRET_KEY Oluşturma:**
   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

5. **PostgreSQL Database Ekleyin:**
   - Dashboard → "New +" → "PostgreSQL"
   - Name: `whatsapp-crm-db`
   - Database: `whatsapp_crm`
   - User: `whatsapp_crm_user`
   - Instance Type: `Free`
   - "Create Database" butonuna tıklayın

6. **DATABASE_URL'yi Web Service'e Bağlayın:**
   - PostgreSQL dashboard'unda "Internal Database URL"yi kopyalayın
   - Web Service'in Environment Variables'ına ekleyin:
     ```
     DATABASE_URL=<internal-database-url>
     ```

7. **Deploy Edin:**
   - "Create Web Service" butonuna tıklayın
   - Deploy işleminin tamamlanmasını bekleyin (5-10 dakika)

8. **Migration'ları Çalıştırın:**
   
   Render dashboard'da "Shell" sekmesine gidin ve şu komutları çalıştırın:
   ```bash
   python migrate_crm_pipeline.py
   python migrate_google_sync.py
   python seed_data.py
   ```

9. **Test Edin:**
   - Render'ın verdiği URL'yi açın (örn: https://whatsapp-crm-saas.onrender.com)
   - Login sayfası görünmeli
   - Varsayılan kullanıcı: `admin@test.com` / `admin123`

## Sorun Giderme

### "git: command not found" Hatası
- Git'i kurduktan sonra PowerShell'i **kapatıp yeniden açın**
- Hala çalışmıyorsa bilgisayarı yeniden başlatın

### "Permission denied" Hatası
- GitHub'da SSH key yerine HTTPS kullanın
- `git remote set-url origin https://github.com/...` komutuyla HTTPS'e geçin

### Render'da "Build Failed" Hatası
- Logs sekmesini kontrol edin
- `requirements.txt` dosyasının doğru olduğundan emin olun
- Python version'ın uyumlu olduğunu kontrol edin

### Database Connection Hatası
- `DATABASE_URL` environment variable'ının doğru olduğundan emin olun
- PostgreSQL database'in "Available" durumda olduğunu kontrol edin

## Yardım

Daha fazla bilgi için:
- **Git Dokümantasyonu:** https://git-scm.com/doc
- **GitHub Guides:** https://guides.github.com/
- **Render Docs:** https://render.com/docs
- **Proje Deployment Guide:** `DEPLOYMENT.md` dosyasına bakın

## Özet Komutlar (Git Kurulduktan Sonra)

```powershell
# 1. Git ayarları
git config --global user.name "Your Name"
git config --global user.email "your@email.com"

# 2. Repository başlat
cd "C:\Users\lordo\OneDrive\Masaüstü\whatsapp crm"
git init
git add .
git commit -m "Initial commit: Ready for Render deployment"

# 3. GitHub'a yükle (GitHub'da repo oluşturduktan sonra)
git remote add origin https://github.com/KULLANICI_ADINIZ/whatsapp-crm-saas.git
git branch -M main
git push -u origin main
```

**Başarılar! 🚀**
