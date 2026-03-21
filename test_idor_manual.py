"""
IDOR Security Manual Test Script
Pytest gerektirmez, direkt Python ile çalışır

Kullanım:
1. Flask uygulamanı başlat: python app.py
2. Başka bir terminal'de: python test_idor_manual.py
"""
import sys
import json

print("=" * 70)
print("IDOR GÜVENLİK TESTİ - MANUEL TEST KILAVUZU")
print("=" * 70)
print()

print("✅ IDOR düzeltmeleri tamamlandı!")
print("   - 16 endpoint güvenli hale getirildi")
print("   - utils/permissions.py merkezi güvenlik altyapısı eklendi")
print()

print("📋 PRODUCTION'A DEPLOY ÖNCESİ YAPILACAK TESTLER:")
print()

print("=" * 70)
print("TEST 1: Cross-Workspace Access (EN KRİTİK)")
print("=" * 70)
print("""
Senaryo: Workspace 2'deki user, Workspace 1'deki deal'e erişmeye çalışıyor

Adımlar:
1. İki farklı workspace oluştur (veya mevcut olanları kullan)
2. Her workspace'te bir deal oluştur
3. Workspace 1'deki deal'in ID'sini not et (örn: 123)
4. Workspace 2'deki user ile login ol
5. Browser console'da şunu çalıştır:

   fetch('/api/v1/deals/123', {
     method: 'GET',
     credentials: 'include'
   })
   .then(r => r.json())
   .then(data => {
     console.log('Response:', data);
     if (data.error) {
       console.log('✅ TEST BAŞARILI: Cross-workspace erişim engellendi');
     } else {
       console.log('❌ TEST BAŞARISIZ: Deal bilgisi görüldü!');
     }
   });

Beklenen: {error: "Deal not found"} veya {error: "Access denied"}
""")

print("=" * 70)
print("TEST 2: Role-Based Access Control")
print("=" * 70)
print("""
Senaryo: Member user, başka birine atanan deal'i güncellemeye çalışıyor

Adımlar:
1. Workspace'te iki user oluştur:
   - User A (owner veya admin)
   - User B (member)
2. User A ile bir deal oluştur (ID'yi not et, örn: 456)
3. User B ile login ol
4. Browser console'da şunu çalıştır:

   fetch('/api/v1/deals/456', {
     method: 'PATCH',
     headers: {'Content-Type': 'application/json'},
     credentials: 'include',
     body: JSON.stringify({name: 'Hacked Deal'})
   })
   .then(r => r.json())
   .then(data => {
     console.log('Response:', data);
     if (data.error && data.error.includes('Access denied')) {
       console.log('✅ TEST BAŞARILI: Member erişim engellendi');
     } else {
       console.log('❌ TEST BAŞARISIZ: Deal güncellendi!');
     }
   });

Beklenen: {error: "Access denied to this deal"}
""")

print("=" * 70)
print("TEST 3: List Endpoint Enumeration")
print("=" * 70)
print("""
Senaryo: Member user sadece kendisine atanan task'ları görmeli

Adımlar:
1. Workspace'te iki user oluştur:
   - User A (owner)
   - User B (member)
2. User A'ya atanmış bir task oluştur (ID: 100)
3. User B'ye atanmış bir task oluştur (ID: 101)
4. User B ile login ol
5. Browser console'da şunu çalıştır:

   fetch('/api/v1/tasks', {
     method: 'GET',
     credentials: 'include'
   })
   .then(r => r.json())
   .then(data => {
     console.log('Tasks:', data.tasks);
     const taskIds = data.tasks.map(t => t.id);
     const hasOwnTask = taskIds.includes(101);
     const hasOthersTask = taskIds.includes(100);
     
     if (hasOwnTask && !hasOthersTask) {
       console.log('✅ TEST BAŞARILI: Sadece kendi task\'ı görüldü');
     } else if (hasOthersTask) {
       console.log('❌ TEST BAŞARISIZ: Başkasının task\'ı görüldü!');
     }
   });

Beklenen: Sadece User B'ye atanan task'lar listelenmeli
""")

print("=" * 70)
print("TEST 4: Viewer Role Restrictions")
print("=" * 70)
print("""
Senaryo: Viewer user hiçbir şeyi düzenleyememeli

Adımlar:
1. Bir user'ın role'ünü 'viewer' yap:
   
   UPDATE users SET role = 'viewer' WHERE email = 'test@example.com';

2. Viewer user ile login ol
3. Bir contact'ı güncellemeyi dene:

   fetch('/api/v1/contacts/789', {
     method: 'PATCH',
     headers: {'Content-Type': 'application/json'},
     credentials: 'include',
     body: JSON.stringify({first_name: 'Hacked'})
   })
   .then(r => r.json())
   .then(data => {
     console.log('Response:', data);
     if (data.error && data.error.includes('Access denied')) {
       console.log('✅ TEST BAŞARILI: Viewer düzenleme yapamadı');
     } else {
       console.log('❌ TEST BAŞARISIZ: Viewer düzenleme yaptı!');
     }
   });

Beklenen: {error: "Access denied to this contact"}
""")

print("=" * 70)
print("TEST 5: Log Kontrolü")
print("=" * 70)
print("""
Senaryo: Erişim reddedildiğinde log yazılmalı

Adımlar:
1. Yukarıdaki testlerden birini yap (örn: cross-workspace access)
2. Flask uygulamanın çalıştığı terminal'e bak
3. Şu log'u görmeli sin:

   WARNING:root:Access denied: user 123 attempted to read deal 456

Eğer bu log'u görmüyorsan:
❌ check_entity_access() fonksiyonu çağrılmıyor demektir!
""")

print("=" * 70)
print("TEST 6: Mevcut Özellikler Çalışıyor mu?")
print("=" * 70)
print("""
Senaryo: IDOR düzeltmeleri mevcut özellikleri bozmadı mı?

Adımlar:
1. Normal bir user ile login ol
2. Şu işlemleri yap:
   ✓ Yeni deal oluştur
   ✓ Deal'i güncelle
   ✓ Deal'i sil
   ✓ Yeni task oluştur
   ✓ Task'ı tamamla
   ✓ Yeni contact oluştur
   ✓ Contact'ı güncelle

Hepsi çalışıyorsa:
✅ Breaking change yok, güvenli!
""")

print("=" * 70)
print("HIZLI SMOKE TEST (5 Dakika)")
print("=" * 70)
print("""
En hızlı test yöntemi:

1. İki farklı browser kullan (Chrome + Firefox veya Incognito)
2. Browser 1: User A ile login ol, bir deal oluştur (ID'yi kopyala)
3. Browser 2: User B ile login ol (farklı workspace)
4. Browser 2'de URL'e direkt deal ID'yi yaz:
   http://localhost:5000/api/v1/deals/[DEAL_ID]
5. Beklenen: 404 Not Found

Eğer deal bilgilerini görüyorsan → HATA VAR!
""")

print("=" * 70)
print("DATABASE KONTROLÜ (Opsiyonel)")
print("=" * 70)
print("""
SQL ile workspace izolasyonunu kontrol et:

-- Workspace 1'deki deal'ler
SELECT id, name, workspace_id FROM deals WHERE workspace_id = 1;

-- Workspace 2'deki deal'ler
SELECT id, name, workspace_id FROM deals WHERE workspace_id = 2;

Her workspace'in kendi entity'leri olmalı.
Cross-workspace entity OLMAMALI!
""")

print()
print("=" * 70)
print("ÖZET")
print("=" * 70)
print("""
✅ Kod değişiklikleri tamamlandı:
   - utils/permissions.py (merkezi güvenlik)
   - routes/pipeline.py (5 deal endpoint)
   - routes/tasks.py (5 task endpoint)
   - routes/contacts.py (6 contact/company endpoint)

✅ Syntax validation geçti:
   - routes/tasks.py: No diagnostics
   - routes/contacts.py: No diagnostics

⏳ Manuel testler yapılacak:
   - Cross-workspace access
   - Role-based access control
   - List endpoint enumeration
   - Viewer restrictions
   - Log kontrolü
   - Mevcut özellikler

🚀 Production'a deploy için:
   1. Yukarıdaki testleri yap
   2. Hepsi geçerse → git commit + push
   3. Render'da deploy olmasını bekle
   4. Production'da da smoke test yap
""")

print()
print("Test yapmaya hazır mısın? (y/n)")
print()
print("Testleri yapmak için:")
print("1. Flask uygulamanı başlat: python app.py")
print("2. Browser'da http://localhost:5000 aç")
print("3. Yukarıdaki test senaryolarını uygula")
print()
print("=" * 70)
