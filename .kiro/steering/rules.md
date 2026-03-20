# PROJE KURALLARI — HER ZAMAN UYGULA

## Proje Kimliği
- **Ad**: WhatsApp CRM SaaS (Enterprise)
- **Repo**: lordon1a/whatsapp-crm-saas
- **Deploy**: Render Free Plan — gevent worker, -w 1, --timeout 120
- **Stack**: Flask + PostgreSQL + SQLAlchemy + Flask-Migrate + gevent + Socket.IO
- **Mimari**: Multi-tenant (workspace_id ile izolasyon), monolitik Flask

## Klasör Yapısı
```
app.py              ← Ana uygulama, gevent monkey_patch EN BAŞTA
routes/             ← Blueprint'ler (pipeline.py, contacts.py, vb.)
models.py           ← Tüm SQLAlchemy modelleri
migrations/         ← Flask-Migrate (Alembic) migration dosyaları
static/             ← app.js, pipeline.js, vb. frontend dosyaları
templates/          ← Jinja2 HTML şablonları
meta_api_client.py  ← WhatsApp Meta API HTTP client (requests kütüphanesi)
```

## Kritik Teknik Notlar
- `from gevent import monkey; monkey.patch_all()` app.py'nin MUTLAK ilk satırları olmalı
- SocketIO async_mode='gevent' olmalı
- Her yeni tablo: workspace_id foreign key ZORUNLU (multi-tenant)
- **DB değişikliklerinde: `flask db migrate` + `flask db upgrade` (db.create_all() YETERSİZ)**
- **models.py'e her kolon/tablo eklendiğinde, aynı görevde flask db migrate + upgrade ZORUNLUDUR. Migrate edilmeden commit yapılmaz.**
- Render Free 512MB RAM — ağır işlem yapma, pool_size=2 tut

## MODEL DEĞİŞİKLİĞİ PROTOKOLÜ (İHLAL EDİLEMEZ)

models.py'e her değişiklik yapıldığında aynı commit'te:
1. `flask db migrate -m "açıklama"` çalıştır
2. `flask db upgrade` çalıştır
3. Migration dosyası (migrations/versions/*.py) commit'e dahil et
4. Migration dosyası olmadan commit YAPMA

Kontrol listesi — her model değişikliğinde sor:
- [ ] Yeni kolon var mı? → migrate et
- [ ] Kolon tipi değişti mi? → migrate et
- [ ] Yeni tablo var mı? → migrate et
- [ ] İlişki değişti mi? → migrate et

## DOKUNMA KURALLARI (EN ÖNEMLİ)
1. Kullanıcı hangi dosyayı belirttiyse SADECE o dosyaya dokun
2. Başka dosyaya dokunmadan önce MUTLAKA sor ve onay al
3. `requirements.txt` ve `Procfile`'a asla otomatik dokunma
4. Migration dosyalarını silme, sadece yeni ekle
5. `monkey_patch_all()` satırını asla taşıma veya kaldırma

## HATA AYIKLAMA PROTOKOLÜ
1. Hata mesajını/traceback'i TAMAMEN oku
2. İlgili dosyayı aç ve ilgili fonksiyonu bul
3. Tahminde bulunma — önce oku, sonra düzelt
4. Yalnızca hatalı satırı değiştir, etrafındaki koda dokunma
5. Aynı hatayı iki kez yaparsan dur ve kullanıcıya açıkla

## GIT KURALLARI
- Her commit TEK bir konuyu kapsamalı
- Commit öncesi ne değiştiğini kullanıcıya söyle
- Push sonrası Render deploy'u bekle, log paylaşılana kadar yorum yapma

## SUPER ADMIN PANELİ
- Route prefix: `/api/super/`
- Ayrı JWT auth — normal session auth ile karışmaz
- Her işlem ImpersonateLog'a yazılır
- `admin_panel/` klasörü ayrı Render servisi olarak deploy edilir
- SuperAdmin modeli normal User modelinden TAMAMEN ayrıdır

## MEVCUT ÇALIŞAN ÖZELLİKLER (DOKUNMA)
- ✅ Socket.IO bağlantısı (gevent ile)
- ✅ Auth sistemi (session-based)
- ✅ Settings endpoint'leri
- ✅ WhatsApp webhook ve mesaj alma
- ✅ Meta API ile mesaj gönderme (meta_api_client.py)
- ✅ Multi-tenant workspace izolasyonu
- ✅ Super admin panel (JWT auth, tenant management, impersonation)

## SIKÇA YAPILAN HATALAR (YAPMA)
- ❌ eventlet import etme — gevent kullanılıyor
- ❌ db.create_all() ile migration yapmaya çalışma
- ❌ Worker sayısını -w 1'den fazla yapma
- ❌ Start command'ı Procfile yerine Dashboard'dan değiştirmeyi unutma
- ❌ **models.py'e kolon ekleyip migrate etmeden commit yapmak — ASLA YAPMA**
- ❌ **Model değişikliğinde app.py'deki run_migrations() fonksiyonunu güncellemeyi unutmak — PRODUCTION ÇÖKER!**

## RENDER FREE TIER ÖZEL KURAL
**Her model değişikliğinde 3 YER güncelle:**
1. Model dosyası (models_crm.py)
2. Migration script (migrations/add_*.py)
3. **app.py → run_migrations() fonksiyonu** ← UNUTMA!

Render Free Tier'da shell yok, sadece startup migration çalışır!
