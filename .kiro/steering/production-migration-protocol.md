---
inclusion: auto
---

# PRODUCTION MIGRATION PROTOCOL (RENDER FREE TIER)

## ⚠️ KRİTİK KURAL: Her Model Değişikliğinde 3 YER GÜNCELLE

Model'e yeni kolon eklerken **MUTLAKA** şu 3 yeri güncelle:

### 1. Model Dosyası (models_crm.py / models.py)
```python
# Yeni kolonu ekle
new_column = db.Column(db.String(100), index=True)
```

### 2. Migration Script (migrations/add_*.py)
```python
# SQLite ve PostgreSQL için migration script oluştur
def migrate_postgres(database_url):
    cur.execute("""
        ALTER TABLE table_name 
        ADD COLUMN new_column VARCHAR(100)
    """)
```

### 3. app.py Auto-Migration Bölümü (ZORUNLU!)
```python
# app.py içindeki run_migrations() fonksiyonuna ekle
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='table_name' AND column_name='new_column'
""")

if not cur.fetchone():
    logger.info("Running migration: add new_column...")
    cur.execute("""
        ALTER TABLE table_name 
        ADD COLUMN new_column VARCHAR(100)
    """)
    conn.commit()
    logger.info("✓ Added new_column")
```

## NEDEN 3 YER?

1. **Model** → SQLAlchemy için gerekli
2. **Migration Script** → Local development için (SQLite)
3. **app.py** → Production için (Render Free Tier'da shell yok!)

## KONTROL LİSTESİ

Her model değişikliğinde bu adımları takip et:

- [ ] Model dosyasına kolonu ekle
- [ ] Migration script oluştur (`migrations/add_*.py`)
- [ ] Migration script'i local'de çalıştır (`python migrations/add_*.py`)
- [ ] **app.py'deki `run_migrations()` fonksiyonuna ekle** ← UNUTMA!
- [ ] Syntax check yap (`getDiagnostics`)
- [ ] Commit yap (3 dosya birlikte)
- [ ] Push yap
- [ ] Render deploy loglarını izle ("✓ All migrations completed" mesajını gör)

## ÖRNEK: Yeni Kolon Ekleme

### Senaryo: contacts tablosuna `linkedin_url` kolonu eklemek istiyoruz

#### 1. models_crm.py
```python
class Contact(db.Model):
    # ... existing fields ...
    linkedin_url = db.Column(db.String(255), nullable=True)
```

#### 2. migrations/add_linkedin_url.py
```python
def migrate_postgres(database_url):
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='contacts' AND column_name='linkedin_url'
    """)
    
    if not cur.fetchone():
        cur.execute("""
            ALTER TABLE contacts 
            ADD COLUMN linkedin_url VARCHAR(255)
        """)
        conn.commit()
        print("✓ Added linkedin_url column")
```

#### 3. app.py (run_migrations fonksiyonu içine)
```python
# Check if linkedin_url column exists
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='contacts' AND column_name='linkedin_url'
""")

if not cur.fetchone():
    logger.info("Running migration: add linkedin_url column...")
    cur.execute("""
        ALTER TABLE contacts 
        ADD COLUMN linkedin_url VARCHAR(255)
    """)
    conn.commit()
    logger.info("✓ Added linkedin_url column")
```

## HATA SENARYOSU

❌ **YANLIŞ:** Sadece model ve migration script ekledim, app.py'yi unuttum
```
Result: Local çalışır ✓
        Production ÇÖKER ❌ (column does not exist hatası)
```

✅ **DOĞRU:** 3 yeri de güncelledim
```
Result: Local çalışır ✓
        Production çalışır ✓
```

## RENDER FREE TIER NOTU

Render Free Tier'da:
- ❌ Shell erişimi YOK
- ❌ Manuel migration çalıştırma YOK
- ✅ Sadece startup'ta otomatik migration çalışır

Bu yüzden **app.py'ye eklemek ZORUNLU!**

## HATIRLATICI

Model değişikliği yaparken şunu sor kendine:

> "app.py'deki run_migrations() fonksiyonuna ekledim mi?"

Cevap HAYIR ise → Production'da ÇÖKECEK!

## QUICK REFERENCE

```bash
# Adım 1: Model güncelle
vim models_crm.py

# Adım 2: Migration script oluştur
vim migrations/add_new_feature.py

# Adım 3: Local'de test et
python migrations/add_new_feature.py

# Adım 4: app.py'ye ekle (UNUTMA!)
vim app.py  # run_migrations() fonksiyonuna ekle

# Adım 5: Commit
git add models_crm.py migrations/add_new_feature.py app.py
git commit -m "Add new feature with production migration"
git push origin main

# Adım 6: Render loglarını izle
# "✓ All migrations completed" mesajını bekle
```

## SON UYARI

Bu protokolü takip etmezsen:
- Local'de her şey çalışır gibi görünür
- Production'da uygulama çöker
- Kullanıcılar hata görür
- Rollback yapmak zorunda kalırsın

**3 YER GÜNCELLE = MUTLU PRODUCTION** 🚀
