# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Drag-and-Drop Sıralama Kaydedilmemesi
  - **CRITICAL**: Bu test UNFIXED kod üzerinde FAIL olmalı - failure bug'ın var olduğunu doğrular
  - **AMAÇ**: Bug'ı gösteren counterexample'ları ortaya çıkarmak
  - **Scoped PBT Approach**: Deterministik bug için property'yi somut failing case'lere scope et
  - Test: Bir contact'ı pozisyon 1'den pozisyon 5'e sürükle → display_order veritabanında güncellenmemeli (Bug Condition'dan)
  - Test: Bir company'yi pozisyon 3'ten pozisyon 1'e sürükle → display_order veritabanında güncellenmemeli
  - Test: POST /api/v1/contacts/reorder endpoint'ini çağır → 404 Not Found dönmeli
  - Test: POST /api/v1/companies/reorder endpoint'ini çağır → 404 Not Found dönmeli
  - Test: Drag-drop sonrası sayfa yenile (F5) → Sıralama eski haline dönmeli
  - Test assertion'ları Expected Behavior Properties ile eşleşmeli (design'dan)
  - UNFIXED kod üzerinde çalıştır
  - **EXPECTED OUTCOME**: Test FAIL olmalı (bu doğru - bug'ın var olduğunu kanıtlar)
  - Counterexample'ları dokümante et (display_order field yok, API endpoint yok, frontend backend'e istek göndermiyor)
  - Test yazıldığında, çalıştırıldığında ve failure dokümante edildiğinde task'ı complete işaretle
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Mevcut İşlevsellik Korunması
  - **IMPORTANT**: Observation-first methodology kullan
  - UNFIXED kod üzerinde non-buggy input'lar için davranışı gözlemle
  - Gözlem: Filtreleme, arama, pagination mevcut haliyle çalışıyor
  - Gözlem: Contact/Company CRUD işlemleri mevcut haliyle çalışıyor
  - Gözlem: Bulk delete ve toplu işlemler mevcut haliyle çalışıyor
  - Gözlem: Contact detail panel ve Company detail modal açılma/kapanma çalışıyor
  - Preservation Requirements'tan gözlemlenen davranış pattern'lerini yakalayan property-based test'ler yaz
  - Property-based testing daha güçlü garanti için birçok test case üretir
  - UNFIXED kod üzerinde test'leri çalıştır
  - **EXPECTED OUTCOME**: Test'ler PASS olmalı (korunacak baseline davranışı doğrular)
  - Test'ler yazıldığında, çalıştırıldığında ve unfixed kod üzerinde pass olduğunda task'ı complete işaretle
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 3. Fix for drag-and-drop sıralama kaydedilmemesi

  - [x] 3.1 models_crm.py'ye display_order alanı ekle
    - Contact modeline `display_order = db.Column(db.Integer, default=0, nullable=False, index=True)` ekle
    - Company modeline `display_order = db.Column(db.Integer, default=0, nullable=False, index=True)` ekle
    - Index ekle (ORDER BY query'leri için performans)
    - _Bug_Condition: isBugCondition(input) where (input.entityType IN ['contact', 'company']) AND (input.action == 'drop') AND (input.newPosition != input.oldPosition) AND NOT displayOrderFieldExists(input.entityType)_
    - _Expected_Behavior: display_order field exists and stores user-defined ordering_
    - _Preservation: Mevcut model field'ları ve ilişkileri değişmemeli_
    - _Requirements: 1.4, 2.4, 2.6_

  - [x] 3.2 Flask migration oluştur ve çalıştır
    - `flask db migrate -m "Add display_order to contacts and companies"` çalıştır
    - `flask db upgrade` çalıştır
    - Mevcut kayıtları sequential display_order değerleriyle backfill et
    - Migration dosyasını commit'e dahil et
    - _Bug_Condition: Database schema'da display_order field eksik_
    - _Expected_Behavior: Migration sonrası display_order field tüm kayıtlarda mevcut olmalı_
    - _Preservation: Mevcut data ve ilişkiler korunmalı_
    - _Requirements: 1.4, 2.4_

  - [x] 3.3 routes/contacts.py'ye reorder endpoint'leri ekle
    - POST /api/v1/contacts/reorder endpoint'i oluştur
    - JSON payload kabul et: `{"contact_ids": [3, 1, 5, 2, 4]}`
    - Her contact için display_order'ı sırayla güncelle
    - workspace_id izolasyonunu doğrula (multi-tenant)
    - Geçersiz contact ID'leri gracefully handle et
    - Success/error response dön
    - POST /api/v1/companies/reorder endpoint'i oluştur
    - JSON payload kabul et: `{"company_ids": [10, 8, 12, 9]}`
    - Her company için display_order'ı sırayla güncelle
    - workspace_id izolasyonunu doğrula
    - Geçersiz company ID'leri gracefully handle et
    - Success/error response dön
    - `@login_required` decorator ekle (auth required)
    - `db.session.commit()` try/except ile wrap et (rollback için)
    - _Bug_Condition: NOT backendReorderAPIExists()_
    - _Expected_Behavior: Backend API yeni sıralamayı kabul edip veritabanına kaydetmeli_
    - _Preservation: Mevcut API endpoint'leri değişmemeli (geriye dönük uyumluluk)_
    - _Requirements: 1.5, 2.1, 2.2, 2.5_

  - [x] 3.4 GET endpoint'lerini display_order'a göre sırala
    - get_contacts() fonksiyonuna `.order_by(Contact.display_order, Contact.first_name)` ekle
    - get_companies() fonksiyonuna `.order_by(Company.display_order, Company.name)` ekle
    - Filtreleme ve arama query'lerinde de display_order sıralamasını koru
    - _Bug_Condition: GET endpoint'leri display_order'ı dikkate almıyor_
    - _Expected_Behavior: Sonuçlar kullanıcının belirlediği sıralamada dönmeli_
    - _Preservation: Filtreleme, arama, pagination mantığı değişmemeli_
    - _Requirements: 2.3, 2.4, 3.4, 3.5_

  - [x] 3.5 Create fonksiyonlarına display_order atama mantığı ekle
    - create_contact() fonksiyonunda yeni contact için `display_order = max(display_order) + 1` ata
    - create_company() fonksiyonunda yeni company için `display_order = max(display_order) + 1` ata
    - workspace_id bazında max değeri hesapla (multi-tenant izolasyon)
    - _Bug_Condition: Yeni kayıtlara display_order atanmıyor_
    - _Expected_Behavior: Yeni kayıtlar otomatik olarak listenin sonuna eklenmeli_
    - _Preservation: Mevcut create mantığı ve validation'lar değişmemeli_
    - _Requirements: 2.6_

  - [x] 3.6 templates/contacts.html ve templates/companies.html'e drag-drop UI ekle
    - SortableJS CDN ekle: `<script src="https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js"></script>`
    - Table row'larına drag handle icon ekle (⋮⋮)
    - `<tr>` elementlerine `draggable="true"` attribute ekle
    - `data-contact-id` veya `data-company-id` data attribute'ları ekle
    - Table body'de SortableJS initialize et
    - `onEnd` event handler'da yeni ID sıralamasını topla
    - POST request gönder: `/api/v1/contacts/reorder` veya `/api/v1/companies/reorder`
    - Success/error toast notification göster
    - _Bug_Condition: Frontend drag-drop event sonrası backend'e istek göndermiyor_
    - _Expected_Behavior: Drag-drop sonrası backend API çağrılmalı ve kullanıcıya feedback verilmeli_
    - _Preservation: Mevcut table rendering, filtreleme UI, pagination UI değişmemeli_
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.5_

  - [x] 3.7 Contacts UI'ını Companies'e benzet (UI tutarlılığı)
    - Contacts page header/toolbar'ı Companies page style'ına uyarla
    - Aynı button style'ları, spacing ve layout kullan
    - Tutarlı icon kullanımı ve color scheme sağla
    - Responsive design korunmalı
    - _Expected_Behavior: İki sayfa görsel olarak tutarlı olmalı_
    - _Preservation: Mevcut functionality değişmemeli, sadece görsel iyileştirme_
    - _Requirements: 2.7_

  - [x] 3.8 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Drag-and-Drop Sıralama Kaydedilmesi
    - **IMPORTANT**: Task 1'deki AYNI test'i tekrar çalıştır - yeni test yazma
    - Task 1'deki test expected behavior'ı encode ediyor
    - Bu test pass olduğunda, expected behavior'ın sağlandığını doğrular
    - Test: Drag-drop sonrası display_order veritabanında güncellenmiş olmalı
    - Test: POST /api/v1/contacts/reorder endpoint'i 200 OK dönmeli
    - Test: POST /api/v1/companies/reorder endpoint'i 200 OK dönmeli
    - Test: Sayfa yenilendikten sonra sıralama korunmalı
    - **EXPECTED OUTCOME**: Test PASS olmalı (bug'ın fix edildiğini doğrular)
    - _Requirements: Expected Behavior Properties from design (2.1, 2.2, 2.3, 2.4, 2.5, 2.6)_

  - [x] 3.9 Verify preservation tests still pass
    - **Property 2: Preservation** - Mevcut İşlevsellik Korunması
    - **IMPORTANT**: Task 2'deki AYNI test'leri tekrar çalıştır - yeni test yazma
    - Task 2'deki preservation property test'lerini çalıştır
    - **EXPECTED OUTCOME**: Test'ler PASS olmalı (regression olmadığını doğrular)
    - Tüm test'lerin fix sonrası hala pass olduğunu doğrula
    - _Requirements: Preservation Requirements from design (3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7)_

- [x] 4. Checkpoint - Ensure all tests pass
  - Tüm test'lerin pass olduğundan emin ol
  - Soru çıkarsa kullanıcıya sor
