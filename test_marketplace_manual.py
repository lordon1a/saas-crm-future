"""
Manual Marketplace Middleware Test
Run this after logging in via browser
"""
import sys

print("""
========================================
MARKETPLACE MIDDLEWARE MANUAL TEST
========================================

Bu testi çalıştırmak için:

1. Tarayıcıda http://localhost:5000 adresine gidin ve login olun
2. Browser DevTools'u açın (F12)
3. Console'a şu komutu yazın:
   document.cookie

4. Aşağıdaki komutları sırayla çalıştırın:

========================================
TEST 1: DocGen'i Kaldır
========================================

fetch('/api/marketplace/uninstall', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({app_slug: 'docgen'})
}).then(r => r.json()).then(console.log)

Beklenen: {"message": "Uygulama kaldırıldı"}

========================================
TEST 2: DocGen Endpoint'ine Eriş (403 Bekleniyor)
========================================

fetch('/api/docgen/templates')
  .then(r => {
    console.log('Status:', r.status);
    return r.text();
  })
  .then(console.log)

Beklenen: Status: 403
         "'docgen' uygulaması bu workspace'te aktif değil."

========================================
TEST 3: DocGen'i Tekrar Yükle
========================================

fetch('/api/marketplace/install', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({app_slug: 'docgen'})
}).then(r => r.json()).then(console.log)

Beklenen: {"message": "Uygulama başarıyla yüklendi"}

========================================
TEST 4: DocGen Endpoint'ine Tekrar Eriş (200 Bekleniyor)
========================================

fetch('/api/docgen/templates')
  .then(r => {
    console.log('Status:', r.status);
    return r.json();
  })
  .then(console.log)

Beklenen: Status: 200
         {templates: [...]}

========================================
SONUÇ
========================================

Eğer:
- TEST 2'de 403 aldıysanız ✓
- TEST 4'te 200 aldıysanız ✓

Middleware çalışıyor demektir! 🎉

========================================
""")
