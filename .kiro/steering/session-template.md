# Kiro Oturum Başlangıç Şablonu
# Her yeni Kiro oturumunda bu mesajı kopyalayıp gönderin
# (köşeli parantezleri doldurun)

---

## KOPYALA-YAPISTIR MESAJI:

Proje bağlamı:
- WhatsApp CRM SaaS, Flask + PostgreSQL + gevent, Render Free Plan
- Repo: lordon1a/whatsapp-crm-saas
- Socket.IO ✅ Auth ✅ Settings ✅ Meta webhook ✅

Şu an çalışmayan: [BUGÜNKÜ SORUNU YAZ]

Kural hatırlatma:
- Sadece söylediğim dosyaya dokun
- DB değişikliği varsa flask db migrate + upgrade çalıştır
- requirements.txt ve Procfile'a sormadan dokunma
- monkey_patch_all() satırına asla dokunma

---

## GÖREV ŞABLONU:
# Her iş verirken bu formatı kullanın:

DOSYA: [routes/pipeline.py]
SORUN: [Tek cümle açıklama]
HATA: [Traceback veya hata mesajı]
YAPILACAK: [Tek bir spesifik değişiklik]
DOKUNMA: [Bu dosyalar dışındakilere kesinlikle dokunma]

---

## MIGRATION ŞABLONU:
# Yeni kolon/tablo eklerken kullanın:

DOSYA: models.py VE migrations/
SORUN: [tablo_adi] tablosuna [kolon_adi] kolonu eksik
YAPILACAK:
  1. models.py'de [Model] sınıfına kolonu ekle
  2. flask db migrate -m "[açıklama]" çalıştır
  3. flask db upgrade çalıştır
  4. migrations/versions/ altındaki yeni dosyayı commit'e ekle
DOKUNMA: app.py, routes/, static/ ve diğer her şey

---

## MODEL DEĞİŞİKLİĞİ ZORUNLU ADIMLAR:
Her models.py değişikliğinde:
```bash
flask db migrate -m "açıklama"
flask db upgrade
git add migrations/versions/*.py
git commit -m "..."
```
Migration dosyası olmadan commit YAPMA!
