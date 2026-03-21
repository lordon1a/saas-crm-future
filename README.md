# WhatsApp-Integrated Enterprise CRM Syste

Bu proje, işletmelerin müşteri ilişkilerini, satış fırsatlarını, görevleri ve iletişim kanallarını (özellikle WhatsApp) tek bir merkezden yönetmesini sağlayan kapsamlı bir Enterprise CRM uygulamasıdır. İçerisindeki otomasyon motoru, pipeline yönetimi ve raporlama özellikleri sayesinde iş akışlarını otomatikleştirir ve satış süreçlerini hızlandırır.

## Özellikler

- **Müşteri ve Şirket Yönetimi (Contacts & Companies):** Müşteri verilerini (isim, rol, lifecycle durumu) ve firmaları (hiyerarşik yapı ile) gelişmiş filtreleme özellikleriyle takip edebilme.
- **Pipeline ve Fırsat (Deal) Yönetimi:** Kanban tahtası mantığı ile satış süreçlerini aşama aşama (stage) yönetme; fırsat kazanma/kaybetme (win/loss reason) analizi yapma.
- **Görev ve Proje Yönetimi (Tasks & Milestones):** Görevlere bitiş tarihi (due date) ekleme, etiketleme, task bağımlılıkları (dependency) kurma ve kilometre taşları (milestones) belirleme.
- **WhatsApp Webhook Entegrasyonu:** Müşterilerden gelen WhatsApp etkileşimlerini doğrudan sistem üzerinden yakalama ve activity history altında saklayabilme.
- **Activity Timeline:** Her bir müşteri (Contact) veya fırsat (Deal) için yapılan e-posta, çağrı, not ve WhatsApp görüşmelerini kronolojik sistem defterinde tutma.
- **Otomasyon Motoru:** Belirli tetikleyicilerde otomatik kuralların (örn. müşteri durumu yenilendiğinde görev atanması veya tag eklenmesi) devreye girmesi.
- **Google & QuickBooks Entegrasyonları:** Google Drive, Google Calendar ve QuickBooks ile harici sistem senkronizasyon yetenekleri.
- **Özel Alanlar (Custom Fields):** Sistem modellerine esnek, sonradan eklenebilen veri tipleri (text, dropdown, date vb.) ekleyebilme.
- **Real-Time Etkileşim:** Socket.IO / WebSockets ile gerçek zamanlı bildirim alınması.

## Teknoloji Stack

- **Backend:** Python, Flask, Flask-SQLAlchemy, Flask-SocketIO (Gevent tabanlı WebSocket)
- **Frontend:** Jinja2 Şablonları (Templates), Tailwind CSS, Vanilla JS
- **Veritabanı:** PostgreSQL (Production), SQLite (Geliştirme için)
- **Deployment:** Render (Gunicorn WSGI & GeventWebSocketWorker kullanımı)

## Kurulum

### Gereksinimler
- Python 3.10 veya üzeri
- PostgreSQL (Production için tavsiye edilir) veya varolan varsayılan SQLite desteği

### Adım Adım Kurulum

1. Repoyu bilgisayarınıza klonlayın ve klasöre girin.
2. İzole bir Python sanal ortamı oluşturun ve aktifleştirin:
   ```bash
   python -m venv venv
   # Windows için:
   venv\Scripts\activate
   # macOS/Linux için:
   source venv/bin/activate
   ```
3. Gerekli bağımlılıkları yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
4. Proje kök dizininde bir `.env` dosyası oluşturun (Aşağıdaki Ortam Değişkenleri bölümüne bakınız).
5. Veritabanı tablolarını oluşturun / Migration işlemlerini yapın:
   ```bash
   flask db upgrade
   ```
   *(Eğer Flask-Migrate ile ilgili sorunlar yaşıyorsanız, basitçe `python app.py` diyerek çalıştığınızda SQLite varsayılan tabloları yaratılacaktır.)*

6. Uygulamayı başlatın (Geliştirme sunucusu):
   ```bash
   flask run
   ```
   ya da `python app.py`

### Ortam Değişkenleri (`.env`)
Uygulamanın ayakta kalabilmesi için asgari olarak aşağıdaki konfigürasyonlara (.env dosyasında) ihtiyaç vardır (Gerçek değerler ile değiştirilebilir):

```ini
FLASK_ENV=development
FLASK_DEBUG=1
DATABASE_URL=sqlite:///whatsapp_crm.db
SECRET_KEY=dev-secret-key-change-in-production
CSRF_SECRET_KEY=default_csrf_secret
# Production'da spesifik domain tanımı yapınız
CORS_ORIGINS=*

# WhatsApp & Webhook Settings
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WEBHOOK_VERIFY_TOKEN=

# API & Sync (Opsiyonel Entegrasyonlar)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
QUICKBOOKS_CLIENT_ID=
```

## Kullanım

- **Dashboard:** Şirketin o anki genel durumunu (Pipeline raporları, son aktiviteler) özetleyen dashboard sayfası ile çalışmaya başlanır.
- **Contacts:** Menüden Kişiler sekmesine gidildiğinde yeni müşteri lead'leri eklenebilir, kişiler detaylarına girilip "Etiketler", "Notlar", "Custom Field'lar" ve "Activity Timeline" üzerinden veri girilebilir.
- **Pipeline:** Fırsatlar Kanban view üzerinde görüntülenip "Open", "Won", "Lost" durumlarına taşınabilir. Kaybedilenler için kayıp sebebi not edilebilir.
- **Tasks & Calendar:** Şirket içi iş yükü Takvim (Calendar) üzerinde yönetilebilir ve takımla paylaşılabilir.

## API Endpoints

Uygulamada standart olarak kullanılan ana API rotaları aşağıdaki gibi gruplanmıştır:

- **Auth**
  - `POST /login` - Kullanıcı girişi
  - `POST /register` - Yeni personel/kullanıcı kaydı
  - `GET /logout` - Sistemden çıkış
- **Contacts & Companies**
  - `GET /api/v1/contacts` - Müşteri listesini filtreli ve sayfalamalı getirme
  - `POST /api/v1/contacts` - Yeni müşteri yaratma
  - `GET /api/v1/companies` - Şirket datasını okuma
- **Deals & Pipeline**
  - `GET /api/v1/pipelines` - Pipeline ve aşamalarını çekme
  - `POST /api/v1/deals` - Yeni satış fırsatı açma
- **Tasks & Collaboration**
  - `GET /api/v1/tasks` - Görevleri okuma (Durum, öncelik gibi filtrelere göre)
  - `POST /api/v1/tasks/<id>/comments` - Görev yorumu ekleme
- **Özel Alanlar (Custom Fields)**
  - `GET /api/v1/custom_fields` - Sistemde tanımlı dinamik alanları okuma
- **Otomasyon & Bildirimler**
  - `POST /webhook` - Meta (WhatsApp) Webhook'ları karşılama rotası
- **Kullanıcı Modülü**
  - `GET /api/me` - Aktif oturum bilgilerini getirme (Kullanıcı verisi)

*(Daha fazlası için `routes/` altındaki blueprint'ler incelenebilir.)*

## Proje Yapısı

```
├── app.py                     # Utama Flask app ve Socket.IO kayıtları (Entrypoint)
├── config.py                  # Tüm çevre değişkenlerinin ve ayarların okunduğu Config sınıfı
├── models.py                  # Çekirdek veritabanı modelleri (Users, Workspaces)
├── models_crm.py              # CRM odaklı modeller (Company, Contact, Deal, Task)
├── models_automation.py       # Otomasyon kural (Rule/Action) modelleri
├── requirements.txt           # Python kütüphane bağımlılıkları
├── Procfile                   # Render platformu için süreç (process) yönetimi talimatları
├── routes/                    # API ve arayüz rotalarının bulunduğu modüler klasör
│   ├── api.py
│   ├── contacts.py            # Müşteri MVC Controller rotaları
│   ├── pipeline.py            # Sales Pipeline Controller rotaları
│   ├── tasks.py               # Görev yönetimi API rotaları
│   └── webhook.py             # Dış sistem entegrasyonu karşılama rotası (Meta API)
├── services/                  # Business Logic (İş Mantığı) katmanı 
│   ├── contact_service.py     # Veritabanı ile MVC arası filtreleme/yazma servisleri
│   └── task_service.py        # Task ve yorum kontrol mantığı
├── static/                    # Frontend assets, JS kütüphaneleri (örn. app.js) ve spesifik scriptler
└── templates/                 # Jinja2 formatındaki HTML render arayüz şablonları
    ├── base.html              
    ├── contacts.html
    ├── pipeline.html
    └── dashboard.html
```

## Deployment (Render)

Proje, Render vb. platformlara anında deploy edilecek yapıda tasarlanmıştır:
1. Render üzerinde `Web Service` seçeneğiyle oluşturun.
2. Build Command olarak `pip install -r requirements.txt` belirleyin.
3. Start Command için `Procfile` dosyasında bulunan gunicorn komutu kullanılmalıdır (Geçerli süreç komutu: `gunicorn app:app --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker --workers 1 --timeout 120 --bind 0.0.0.0:$PORT` vb. olarak alınır).
4. `config.py` içinde ve Render arayüzünde Environment (PostgreSQL veritabanı URL vs.) değişkenlerini tanımlamayı unutmayın.
5. `app.py` içerisindeki `run_migrations()` fonksiyonu sayesinde Render üzerinde PostgeSQL için tablo/kolon yapıları başlangıçta otonom denetlenmektedir.

## Güvenlik

Sistemde çok sayıda katı güvenlik standartı uygulanmıştır:
- **CSRF Koruması (Cross-Site Request Forgery):** Tüm state değiştiren sorgularda `Flask-WTF` tarafından CSRF tabanlı token doğrulaması zorunludur.
- **Rate Limit Koruması:** Login endpoint'i gibi kritik alanlarda Brute-force denemelerini engellemek amacıyla `Flask-Limiter` devrededir.
- **SQL Injection:** Tüm veritabanı etkileşimleri ORM katmanında (SQLAlchemy) parametrelendirilerek güvenli halde icra edilmektedir.
- **Cookie Security:** Production tarafında HTTPOnly ve Secure flag ayarları `config.py` tarafından zorunlu kılınmıştır.
- **XSS Savunması:** Frontend üzerinde alınan girdilerin Render alanlarına girerken `escapeHtml` yardımcı fonksiyonundan geçirilmesi prensibi uygulanmaktadır.

## Katkıda Bulunma

1. Projeyi kendi tarafınıza **Fork** edin.
2. Yeni özellik veya hata düzeltmesi için bir Feature Branch açın (`git checkout -b feature/HarikaOzellik`).
3. Değişiklikleri taahhüt edin (`git commit -m 'Yeni harika özellik eklendi'`).
4. Branch'i uzak sunucuya gönderin (`git push origin feature/HarikaOzellik`).
5. Reponuzdan bir Pull Request (PR) açarak ana dallara (main/master) birleştirme talep edin.
