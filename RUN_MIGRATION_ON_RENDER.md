# Production Migration Talimatları

## SORUN
Production PostgreSQL veritabanında `lead_source`, `lifecycle_stage`, `qualified_at`, `converted_at` kolonları eksik.

## ÇÖZÜM
Render Dashboard'dan migration script'ini çalıştırın:

### Adım 1: Render Dashboard'a Girin
1. https://dashboard.render.com adresine gidin
2. `whatsapp-crm-saas` servisinizi seçin

### Adım 2: Shell Açın
1. Sağ üstteki "Shell" butonuna tıklayın
2. Terminal açılacak

### Adım 3: Migration Çalıştırın
Terminalde şu komutu çalıştırın:

```bash
python migrations/add_lead_management_fields.py
```

### Beklenen Çıktı:
```
Connected to PostgreSQL database successfully

Adding lead management columns to contacts table...
✓ Added lead_source column to contacts
✓ Added lifecycle_stage column to contacts
✓ Added qualified_at column to contacts
✓ Added converted_at column to contacts
✓ Created indexes on lead management columns

✓ PostgreSQL migration completed successfully
```

### Adım 4: Servisi Yeniden Başlatın (Opsiyonel)
Migration tamamlandıktan sonra servisi yeniden başlatmak için:
- "Manual Deploy" > "Clear build cache & deploy" seçeneğini kullanabilirsiniz
- VEYA sadece bekleyin, bir sonraki request'te otomatik çalışacak

## Alternatif: Otomatik Migration
Eğer her deploy'da otomatik migration çalışmasını istiyorsanız:

### app.py'ye ekleyin (ÖNERİLMEZ - manuel kontrol daha güvenli):
```python
# Startup'ta migration çalıştır
if os.environ.get('RUN_MIGRATIONS_ON_STARTUP') == '1':
    try:
        import subprocess
        subprocess.run(['python', 'migrations/add_lead_management_fields.py'], check=True)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
```

## Doğrulama
Migration başarılı olduktan sonra:
1. https://whatsapp-crm-saas.onrender.com/contacts sayfasını yenileyin
2. Hata kaybolmalı
3. Contacts listesi normal şekilde yüklenmeli

## Notlar
- Migration idempotent (tekrar çalıştırılabilir) - zaten varsa "already exists" der
- Downgrade için: `python migrations/add_lead_management_fields.py downgrade`
- SQLite (local) zaten çalıştırıldı ✓
- PostgreSQL (production) çalıştırılması gerekiyor ⚠️
