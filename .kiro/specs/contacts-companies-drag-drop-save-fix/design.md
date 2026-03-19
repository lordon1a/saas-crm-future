# Contacts ve Companies Drag-and-Drop Kaydetme Bugfix Design

## Overview

Contacts ve Companies sayfalarında drag-and-drop (tut-bırak) özelliği frontend'de görsel olarak çalışıyor ancak değişiklikler veritabanına kaydedilmiyor. Kullanıcı bir kişiyi veya şirketi sürükleyip başka bir satırın yerine bıraktığında, sayfa yenilendiğinde (F5) öğeler eski konumlarına geri dönüyor.

Bu bug üç temel eksiklikten kaynaklanıyor:
1. Contact ve Company modellerinde `display_order` alanı eksik
2. Backend'de sıralama kaydetme API endpoint'i yok
3. Frontend'de drag-and-drop sonrası backend'e veri gönderen kod eksik

Ek olarak, Contacts sayfasının UI'ı Companies sayfasına benzetilecek (UI tutarlılığı için).

## Glossary

- **Bug_Condition (C)**: Kullanıcının drag-and-drop ile sıralama değiştirmesi ancak değişikliklerin veritabanına kaydedilmemesi durumu
- **Property (P)**: Drag-and-drop sonrası yeni sıralama bilgisinin veritabanına kaydedilmesi ve sayfa yenilendiğinde korunması
- **Preservation**: Mevcut listeleme, filtreleme, arama, pagination ve diğer CRUD işlemlerinin aynen çalışmaya devam etmesi
- **display_order**: Contact ve Company tablolarına eklenecek integer alan - kullanıcının belirlediği sıralamayı saklar
- **Drag-and-Drop**: HTML5 Drag and Drop API veya SortableJS gibi kütüphane ile satırları sürükleyip bırakma özelliği
- **Reordering API**: Backend'de POST /api/v1/contacts/reorder ve POST /api/v1/companies/reorder endpoint'leri

## Bug Details

### Bug Condition

Bug, kullanıcı Contacts veya Companies sayfasında bir satırı sürükleyip başka bir konuma bıraktığında ortaya çıkıyor. Frontend görsel olarak satırları yeniden sıralıyor ancak bu değişiklik backend'e gönderilmiyor ve veritabanına kaydedilmiyor.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type DragDropEvent
  OUTPUT: boolean
  
  RETURN (input.entityType IN ['contact', 'company'])
         AND (input.action == 'drop')
         AND (input.newPosition != input.oldPosition)
         AND NOT backendReorderAPIExists()
         AND NOT displayOrderFieldExists(input.entityType)
END FUNCTION
```

### Examples

- **Contact Drag-Drop**: Kullanıcı "Ali Yılmaz" kişisini 1. sıradan 5. sıraya sürükler → Görsel olarak hareket eder → Sayfa yenilendiğinde "Ali Yılmaz" tekrar 1. sıraya döner
- **Company Drag-Drop**: Kullanıcı "Acme Corp" şirketini 3. sıradan 1. sıraya sürükler → Görsel olarak hareket eder → Sayfa yenilendiğinde "Acme Corp" tekrar 3. sıraya döner
- **Multiple Reorders**: Kullanıcı 5 farklı kişiyi yeniden sıralar → Hepsi görsel olarak hareket eder → Sayfa yenilendiğinde tüm değişiklikler kaybolur
- **Edge Case - Pagination**: Kullanıcı 1. sayfadaki bir kişiyi sürükler, 2. sayfaya geçer, geri döner → Sıralama kaybolmuştur

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Mevcut GET /api/v1/contacts ve GET /api/v1/companies endpoint'leri aynen çalışmalı (geriye dönük uyumluluk)
- Filtreleme, arama, pagination özellikleri değişmemeli
- Contact ve Company oluşturma, güncelleme, silme işlemleri aynen çalışmalı
- Contact detail panel ve Company detail modal açılma/kapanma davranışları değişmemeli
- Bulk delete ve diğer toplu işlemler aynen çalışmalı
- Mevcut sıralama seçenekleri (ad, tarih, vb.) çalışmaya devam etmeli

**Scope:**
Drag-and-drop özelliğini kullanmayan tüm işlemler tamamen etkilenmemeli. Bu şunları içerir:
- Normal listeleme ve görüntüleme
- Arama ve filtreleme
- Sayfa geçişleri (pagination)
- CRUD işlemleri (Create, Read, Update, Delete)
- Export/Import işlemleri

## Hypothesized Root Cause

Bug açıklamasına ve kod incelemesine dayanarak, en olası nedenler:

1. **Missing Database Field**: Contact ve Company modellerinde `display_order` integer alanı tanımlı değil
   - models_crm.py'de Contact ve Company sınıflarında bu alan yok
   - Migration dosyası oluşturulmamış

2. **Missing Backend API**: Sıralama kaydetme endpoint'leri yok
   - routes/contacts.py'de POST /api/v1/contacts/reorder endpoint'i yok
   - POST /api/v1/companies/reorder endpoint'i yok
   - Bulk update mantığı yazılmamış

3. **Missing Frontend Code**: Drag-and-drop event handler'ları eksik veya backend'e istek göndermiyor
   - HTML'de drag-and-drop event listener'ları yok veya eksik
   - JavaScript'te drop event sonrası backend API çağrısı yapılmıyor
   - SortableJS veya benzeri kütüphane kullanılmamış olabilir

4. **Missing Default Value Logic**: Yeni kayıt oluşturulurken display_order otomatik atanmıyor
   - ContactService.create_contact() ve create_company() fonksiyonlarında display_order atama mantığı yok

## Correctness Properties

Property 1: Bug Condition - Drag-and-Drop Sıralama Kaydedilmesi

_For any_ drag-and-drop event where a contact or company is moved to a new position, the fixed system SHALL save the new display_order values to the database via a backend API call, and the new ordering SHALL persist after page refresh.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**

Property 2: Preservation - Mevcut İşlevsellik Korunması

_For any_ operation that does NOT involve drag-and-drop reordering (filtering, searching, pagination, CRUD operations), the fixed system SHALL produce exactly the same behavior as the original system, preserving all existing functionality.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `models_crm.py`

**Function**: `Contact` and `Company` model classes

**Specific Changes**:
1. **Add display_order Field to Contact Model**:
   - Add `display_order = db.Column(db.Integer, default=0, nullable=False, index=True)` to Contact class
   - Index for performance on ORDER BY queries

2. **Add display_order Field to Company Model**:
   - Add `display_order = db.Column(db.Integer, default=0, nullable=False, index=True)` to Company class
   - Index for performance on ORDER BY queries

3. **Create Migration Script**:
   - Run `flask db migrate -m "Add display_order to contacts and companies"`
   - Run `flask db upgrade`
   - Backfill existing records with sequential display_order values

**File**: `routes/contacts.py`

**Function**: New endpoint functions

**Specific Changes**:
1. **Add Contacts Reorder Endpoint**:
   - Create `@contacts_bp.route('/api/v1/contacts/reorder', methods=['POST'])`
   - Accept JSON payload: `{"contact_ids": [3, 1, 5, 2, 4]}`
   - Update display_order for each contact in order
   - Return success/error response

2. **Add Companies Reorder Endpoint**:
   - Create `@contacts_bp.route('/api/v1/companies/reorder', methods=['POST'])`
   - Accept JSON payload: `{"company_ids": [10, 8, 12, 9]}`
   - Update display_order for each company in order
   - Return success/error response

3. **Update GET Endpoints to Order by display_order**:
   - Modify `get_contacts()` to add `.order_by(Contact.display_order, Contact.first_name)`
   - Modify `get_companies()` to add `.order_by(Company.display_order, Company.name)`

4. **Update Create Functions to Set display_order**:
   - Modify `create_contact()` to set `display_order = max(display_order) + 1`
   - Modify `create_company()` to set `display_order = max(display_order) + 1`

**File**: `templates/contacts.html` and `templates/companies.html`

**Function**: HTML table structure

**Specific Changes**:
1. **Add Drag Handle to Table Rows**:
   - Add drag handle icon (⋮⋮) to first column
   - Add `draggable="true"` attribute to `<tr>` elements
   - Add data attributes: `data-contact-id` or `data-company-id`

2. **Add SortableJS Library**:
   - Include SortableJS CDN: `<script src="https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js"></script>`

3. **Add JavaScript Drag-Drop Handler**:
   - Initialize SortableJS on table body
   - On `onEnd` event, collect new order of IDs
   - Send POST request to `/api/v1/contacts/reorder` or `/api/v1/companies/reorder`
   - Show success/error toast notification

4. **UI Consistency - Contacts Page**:
   - Update Contacts page header/toolbar to match Companies page style
   - Use same button styles, spacing, and layout
   - Ensure consistent icon usage and color scheme

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate drag-and-drop events and verify that the new order is NOT persisted in the database on unfixed code. Run these tests to observe failures and understand the root cause.

**Test Cases**:
1. **Contact Reorder Test**: Drag contact from position 1 to position 5 → Verify display_order NOT updated in DB (will fail on unfixed code)
2. **Company Reorder Test**: Drag company from position 3 to position 1 → Verify display_order NOT updated in DB (will fail on unfixed code)
3. **Page Refresh Test**: Reorder contacts → Refresh page → Verify order reverts to original (will fail on unfixed code)
4. **API Missing Test**: Try to call POST /api/v1/contacts/reorder → Verify 404 Not Found (will fail on unfixed code)

**Expected Counterexamples**:
- display_order field does not exist in database schema
- POST /api/v1/contacts/reorder returns 404 Not Found
- After drag-drop, no backend API call is made (observable in browser DevTools Network tab)
- After page refresh, order reverts to original (alphabetical or creation date)

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL dragDropEvent WHERE isBugCondition(dragDropEvent) DO
  result := handleDragDrop_fixed(dragDropEvent)
  ASSERT result.backendAPICalled == true
  ASSERT result.displayOrderUpdated == true
  ASSERT result.persistsAfterRefresh == true
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL operation WHERE NOT isBugCondition(operation) DO
  ASSERT originalBehavior(operation) == fixedBehavior(operation)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-drag-drop operations

**Test Plan**: Observe behavior on UNFIXED code first for filtering, searching, pagination, and CRUD operations, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Filtering Preservation**: Apply various filters → Verify results match unfixed code behavior
2. **Search Preservation**: Search for contacts/companies → Verify results match unfixed code behavior
3. **Pagination Preservation**: Navigate between pages → Verify page transitions work identically
4. **CRUD Preservation**: Create, update, delete contacts/companies → Verify operations work identically
5. **Bulk Operations Preservation**: Bulk delete, bulk edit → Verify operations work identically

### Unit Tests

- Test display_order field exists in Contact and Company models
- Test default display_order value is set on new record creation
- Test POST /api/v1/contacts/reorder endpoint accepts valid payload
- Test POST /api/v1/companies/reorder endpoint accepts valid payload
- Test reorder endpoint validates workspace_id isolation
- Test reorder endpoint handles invalid contact/company IDs gracefully
- Test GET endpoints return results ordered by display_order

### Property-Based Tests

- Generate random drag-drop sequences and verify all are persisted correctly
- Generate random contact/company lists and verify reordering works for any list size
- Generate random workspace_id values and verify multi-tenant isolation is preserved
- Test that filtering + reordering works correctly across many filter combinations
- Test that pagination + reordering works correctly across many page sizes

### Integration Tests

- Test full drag-drop flow: drag → drop → backend call → database update → page refresh → verify order
- Test drag-drop in Contacts page with various filters applied
- Test drag-drop in Companies page with search query active
- Test drag-drop with pagination (reorder on page 1, navigate to page 2, return to page 1)
- Test UI consistency between Contacts and Companies pages
- Test that export/import preserves display_order values
