# Implementation Tasks: Modern CRM Filter System

## Overview

Bu task listesi, Modern CRM Filter System'in 4 fazlı implementasyonunu içerir. Sistem, Contacts ve Companies sayfalarındaki filter sistemini tamamen yenileyerek modern, responsive, performanslı ve güvenli bir filtreleme deneyimi sağlar.

**Önemli Notlar:**
- Tüm DB modelleri zaten mevcut (SavedFilter, UserDefinedFilter, FilterExecutionLog) - migration gerekmez
- Backend: Python/Flask, Frontend: JavaScript/Tailwind CSS
- Test task'ları optional olarak işaretlenmiştir (*)
- Her checkpoint'te testlerin geçtiğinden emin olun

## Tasks

### Phase 1: Backend Foundation

- [ ] 1. Backend servis katmanı refactoring
  - [ ] 1.1 FilterService refactor - filter conflict çözümü
    - `services/filter_service.py` dosyasını refactor et
    - `build_query()` metodundaki filter çakışma sorunlarını çöz
    - Unified query builder implementasyonu (tek WHERE clause builder)
    - Filter operator'ları için lambda fonksiyonları ekle (equals, not_equals, contains, starts_with, ends_with, greater_than, less_than, between, in, not_in, is_null, is_not_null)
    - `validate_filters()` metodunu ekle - field, operator, value validation
    - `apply_filters()` metodunu güncelle - pagination, sorting, workspace isolation
    - `evaluate_quick_filter()` metodunu ekle - quick filter definitions
    - Performance logging ekle (execution_time_ms, result_count)
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 6.1, 6.2_
  
  - [ ]* 1.2 FilterService için property test yaz
    - **Property 1: Starred Filter Correctness**
    - **Property 4: AND Logic Correctness**
    - **Property 6: Filter Execution Logging**
    - **Property 7: Null Value Handling**
    - **Validates: Requirements 2.1, 3.1, 3.5, 3.6**
  
  - [ ] 1.3 FilterValidationService oluştur (YENİ)
    - `services/filter_validation_service.py` dosyasını oluştur
    - `validate_field_name()` - whitelist kontrolü (ALLOWED_CONTACT_FIELDS, ALLOWED_COMPANY_FIELDS)
    - `validate_operator()` - operator whitelist kontrolü
    - `validate_value_type()` - value type validation (string, int, bool, date, list)
    - `sanitize_value()` - SQL injection prevention
    - `check_workspace_access()` - workspace isolation kontrolü
    - `check_rate_limit()` - rate limiting kontrolü
    - _Requirements: 15.1, 15.4, 15.5, 15.6_
  
  - [ ]* 1.4 FilterValidationService için unit test yaz
    - Test invalid field rejection
    - Test invalid operator rejection
    - Test value type mismatch
    - Test SQL injection prevention
    - Test workspace isolation
    - **Validates: Requirements 15.4, 15.5, 15.6**

- [ ] 2. Cache servisi implementasyonu
  - [ ] 2.1 FilterCacheService oluştur (YENİ)
    - `services/filter_cache_service.py` dosyasını oluştur
    - In-memory cache dict yapısı: `{cache_key: {'data': results, 'expires_at': timestamp}}`
    - `generate_cache_key()` - entity_type, filters, workspace_id'den hash oluştur
    - `get_cached_results()` - cache lookup ve expiry kontrolü
    - `set_cached_results()` - cache storage (TTL: 300 saniye)
    - `invalidate_cache()` - entity_type ve workspace_id bazlı invalidation
    - `cleanup_expired()` - expired cache entries temizleme
    - _Requirements: 6.4, 18.7_
  
  - [ ]* 2.2 FilterCacheService için property test yaz
    - **Property 16: Query Result Caching**
    - **Property 49: Preview Count Caching**
    - **Validates: Requirements 6.4, 18.7**

- [ ] 3. API endpoint güncellemeleri
  - [ ] 3.1 routes/contacts.py güncelle
    - GET /api/v1/contacts endpoint'ini güncelle
    - Query parameters: filters (JSON), quick_filter, page, per_page, sort_by, sort_order
    - Response'a `applied_filters` objesi ekle
    - FilterService.apply_filters() kullan
    - FilterCacheService entegrasyonu
    - Error handling iyileştir (400, 401, 403, 500)
    - Rate limiting ekle (@rate_limit decorator)
    - _Requirements: 16.1, 16.3, 16.4, 16.7_
  
  - [ ] 3.2 routes/companies.py güncelle
    - GET /api/v1/companies endpoint'ini güncelle (contacts ile aynı yapı)
    - Query parameters ve response yapısı contacts ile aynı
    - FilterService.apply_filters() kullan (entity_type='company')
    - Error handling ve rate limiting ekle
    - _Requirements: 16.2, 16.3, 16.4, 16.7_
  
  - [ ]* 3.3 API endpoint'leri için unit test yaz
    - Test successful filter request
    - Test invalid filter parameters (400)
    - Test unauthorized access (401)
    - Test cross-workspace access (403)
    - Test applied_filters in response
    - **Validates: Requirements 16.3, 16.4, 16.5, 16.6, 16.7**

- [ ] 4. Checkpoint - Backend foundation tamamlandı
  - Tüm backend testlerin geçtiğinden emin ol
  - FilterService conflict çözümünü manuel test et
  - Workspace isolation'ı doğrula
  - Kullanıcıya sorular varsa sor

### Phase 2: Frontend UI Components

- [ ] 5. FilterPanel component refactoring
  - [ ] 5.1 FilterPanel.js'i tamamen yeniden yaz
    - `static/filter-panel.js` dosyasını refactor et
    - Modern class-based component yapısı
    - Constructor: `constructor(entityType, containerId)`
    - State management: activeFilters, quickFilters, savedFilters, isCollapsed
    - `init()` - component initialization, event listeners
    - `render()` - full UI render (quick filters, active chips, add filter form, saved filters)
    - `applyQuickFilter(filterName)` - quick filter activation
    - `addFilter(field, operator, value)` - manual filter ekleme
    - `removeFilter(field)` - filter kaldırma
    - `clearAll()` - tüm filtreleri temizle
    - `toggleCollapse()` - panel collapse/expand
    - Responsive layout: desktop (sidebar), mobile (bottom sheet)
    - Touch gesture support: swipe-down to close on mobile
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7, 14.1, 14.2_
  
  - [ ] 5.2 FilterPanel state management implementasyonu
    - `saveToSession()` - localStorage'a kaydet
    - `restoreFromSession()` - localStorage'dan yükle
    - `restoreFromURL()` - URL query parameters'dan yükle
    - `syncToURL()` - URL'i güncelle
    - Cross-tab synchronization (localStorage events)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.7_
  
  - [ ]* 5.3 FilterPanel için unit test yaz
    - Test quick filter button rendering
    - Test filter chip creation
    - Test filter removal
    - Test clear all
    - Test collapse/expand
    - Test responsive layout
    - **Validates: Requirements 1.1, 1.3, 4.1, 4.2, 7.1**

- [ ] 6. FilterChips component oluşturma (YENİ)
  - [ ] 6.1 FilterChips.js implementasyonu
    - `static/filter-chips.js` dosyasını oluştur
    - Constructor: `constructor(containerId)`
    - `render(activeFilters)` - chip'leri render et
    - `getChipColor(fieldType)` - field type'a göre renk (text: blue, number: green, date: purple, boolean: orange)
    - `formatChipLabel(field, operator, value)` - human-readable label
    - `attachRemoveHandlers()` - close button event listeners
    - Chip yapısı: `<div class="filter-chip"><span>Label</span><button>×</button></div>`
    - Tooltip support (hover için full filter details)
    - Fade-in/fade-out animations (200ms)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_
  
  - [ ]* 6.2 FilterChips için unit test yaz
    - Test chip rendering
    - Test chip color coding
    - Test chip removal
    - Test tooltip display
    - **Validates: Requirements 4.1, 4.2, 4.4, 4.6**

- [x] 7. Quick filter UI implementasyonu
  - [x] 7.1 Quick filter butonları ve count badges
    - FilterPanel.js içinde quick filter butonlarını render et
    - Button yapısı: icon + label + count badge
    - Active state styling (bg-blue-100, border-blue-500)
    - Hover effects ve loading states
    - Horizontal scrollable container on mobile
    - Keyboard navigation support (Tab, Enter)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  
  - [ ]* 7.2 Quick filter için unit test yaz
    - Test button rendering
    - Test count badge display
    - Test active state
    - Test keyboard navigation
    - **Validates: Requirements 7.1, 7.3, 7.4, 7.6**

- [x] 8. Search functionality implementasyonu
  - [x] 8.1 Global search input ve suggestions
    - FilterPanel.js içinde search input ekle
    - Debouncing (300ms delay)
    - Multi-field search: contacts (first_name, last_name, email, phone, whatsapp_phone, job_title, company_name), companies (name, industry, website, phone, address)
    - Case-insensitive ILIKE queries
    - Search suggestions dropdown (minimum 2 characters)
    - Result highlighting (frontend - <mark> tag)
    - Clear button (×) in search input
    - "No results found" message
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_
  
  - [ ]* 8.2 Search için property test yaz
    - **Property 11: Multi-Field Contact Search**
    - **Property 12: Multi-Field Company Search**
    - **Property 13: Case-Insensitive Search**
    - **Property 14: Search Result Highlighting**
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5**

- [ ] 9. Template güncellemeleri
  - [x] 9.1 templates/contacts.html güncelle
    - Filter panel container ekle: `<div id="filter-panel-container"></div>`
    - Filter chips display area ekle: `<div id="filter-chips-container"></div>`
    - FilterPanel initialization script ekle
    - Responsive layout: sidebar on desktop, bottom sheet on mobile
    - Touch target size: minimum 44x44px on mobile
    - _Requirements: 1.1, 1.4, 14.1, 14.3, 14.7_
  
  - [x] 9.2 templates/companies.html güncelle
    - contacts.html ile aynı yapı
    - FilterPanel initialization (entityType='company')
    - _Requirements: 1.1, 1.4, 14.1, 14.3, 14.7_

- [ ] 10. Checkpoint - Frontend UI tamamlandı
  - Tüm frontend testlerin geçtiğinden emin ol
  - Responsive design'ı tüm cihazlarda test et
  - Touch gestures'ı mobile'da test et
  - Keyboard navigation'ı test et
  - Kullanıcıya sorular varsa sor

### Phase 3: Advanced Features

- [x] 11. Saved filters API ve UI
  - [x] 11.1 routes/filters.py oluştur (YENİ)
    - `routes/filters.py` dosyasını oluştur
    - GET /api/v1/saved-filters - user's filters + shared team filters
    - POST /api/v1/saved-filters - create new saved filter
    - PATCH /api/v1/saved-filters/:id - update filter (only owner)
    - DELETE /api/v1/saved-filters/:id - delete filter (only owner)
    - POST /api/v1/saved-filters/:id/duplicate - duplicate shared filter
    - Query parameter: entity_type (required)
    - Permission checks: user_id ownership validation
    - Filter limit enforcement: 50 per user per entity_type
    - _Requirements: 12.1, 12.2, 12.3, 12.6, 12.7, 12.8_
  
  - [x] 11.2 SavedFilterService güncelle
    - `services/saved_filter_service.py` dosyasını güncelle (zaten mevcut)
    - `create_filter()` - filter limit check (50 per user)
    - `get_user_filters()` - user's own filters
    - `get_shared_filters()` - workspace shared filters
    - `update_filter()` - ownership check
    - `delete_filter()` - ownership check
    - `share_filter()` - set is_shared=true
    - `duplicate_filter()` - copy shared filter to user's filters
    - _Requirements: 12.3, 12.6, 12.7, 12.8, 20.2, 20.6_
  
  - [x] 11.3 Saved filters UI implementasyonu
    - FilterPanel.js içinde "Save Filter" button ekle
    - Save modal: name, description, is_shared checkbox
    - Saved filters dropdown: search functionality
    - Filter metadata display: name, description, created date, creator name
    - Edit/delete buttons (only for owner)
    - Duplicate button (for shared filters)
    - "Team Filters" section (separate from user's filters)
    - _Requirements: 12.1, 12.2, 12.4, 12.5, 12.6, 12.7, 20.3, 20.4, 20.5, 20.6_
  
  - [ ]* 11.4 Saved filters için unit test yaz
    - Test filter creation
    - Test filter limit enforcement
    - Test edit permission (only owner)
    - Test delete permission (only owner)
    - Test filter duplication
    - Test shared filter visibility
    - **Validates: Requirements 12.3, 12.6, 12.7, 12.8, 20.2, 20.5**

- [ ] 12. Filter sharing implementasyonu
  - [x] 12.1 Filter sharing logic
    - SavedFilterService.share_filter() kullan
    - is_shared=true set et
    - Workspace users'a notification gönder (optional - future)
    - Team filters section'da göster
    - Creator name ve creation date display
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.7_
  
  - [ ]* 12.2 Filter sharing için property test yaz
    - **Property 54: Shared Filter Visibility**
    - **Property 55: Shared Filter Creator Display**
    - **Property 56: Shared Filter Edit Permission**
    - **Property 57: Shared Filter Duplication**
    - **Validates: Requirements 20.2, 20.4, 20.5, 20.6**

- [ ] 13. Export functionality implementasyonu
  - [x] 13.1 FilterExport component oluştur (YENİ)
    - `static/filter-export.js` dosyasını oluştur
    - Constructor: `constructor(entityType)`
    - `openExportModal(format)` - export modal'ı aç
    - `selectColumns()` - column selection UI
    - `exportData(format, columns, filters)` - export request gönder
    - `showProgress()` - progress indicator
    - `downloadFile(blob, filename)` - file download
    - Export formats: CSV, Excel (XLSX)
    - Column selection: checkboxes for all available columns
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.7_
  
  - [x] 13.2 Export API endpoints
    - routes/contacts.py'a POST /api/v1/contacts/export ekle
    - routes/companies.py'a POST /api/v1/companies/export ekle
    - Request body: filters, format, columns
    - FilterService.export_to_csv() ve export_to_excel() implementasyonu
    - Export limit: 10,000 records
    - Rate limiting: 10 requests per hour
    - Filename format: "contacts_filtered_2024-01-15.csv"
    - _Requirements: 13.5, 13.6, 13.8_
  
  - [ ]* 13.3 Export için unit test yaz
    - Test CSV export
    - Test Excel export
    - Test export limit enforcement (10,000 records)
    - Test column selection
    - Test filename format
    - **Validates: Requirements 13.5, 13.6, 13.8**

- [ ] 14. Filter history implementasyonu
  - [x] 14.1 Filter history localStorage management
    - FilterPanel.js içinde history management ekle
    - localStorage'da son 10 filter configuration'ı sakla
    - Deduplication logic (aynı filter varsa en son olanı tut)
    - Timestamp tracking (last used)
    - "Recent Filters" dropdown UI
    - Filter name (if saved) veya auto-generated description
    - Clear history button
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_
  
  - [ ]* 14.2 Filter history için property test yaz
    - **Property 50: Filter History Size Limit**
    - **Property 51: Recent Filter Display**
    - **Property 52: Recent Filter Timestamp Display**
    - **Property 53: Filter History Deduplication**
    - **Validates: Requirements 19.1, 19.3, 19.5, 19.7**

- [ ] 15. Advanced filter controls
  - [ ] 15.1 Date range picker implementasyonu
    - FilterPanel.js içinde date range picker ekle
    - Calendar view (modern date picker library kullan veya custom)
    - Preset ranges: "Today", "Yesterday", "Last 7 Days", "Last 30 Days", "This Month", "Last Month", "This Year", "Custom Range"
    - Human-readable format: "Jan 1, 2024 - Jan 31, 2024"
    - Timezone conversion (workspace timezone)
    - Validation: start_date <= end_date
    - Today's date highlighting
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_
  
  - [ ] 15.2 Numeric range slider implementasyonu
    - FilterPanel.js içinde dual-handle range slider ekle (lead_score: 0-100)
    - Slider ve numeric input synchronization (bidirectional)
    - Min/max value display
    - Validation: min <= max
    - Visual indicator of selected range
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_
  
  - [ ] 15.3 Multi-select dropdown implementasyonu
    - FilterPanel.js içinde searchable multi-select dropdown ekle
    - Fields: role, industry, size
    - Selected values as chips inside dropdown
    - Keyboard navigation (Arrow keys, Enter, Escape)
    - "Select All" ve "Clear All" options
    - Selected count display in trigger button
    - Search highlighting
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  
  - [ ]* 15.4 Advanced controls için unit test yaz
    - Test date range validation
    - Test numeric range validation
    - Test multi-select functionality
    - Test keyboard navigation
    - **Validates: Requirements 9.6, 10.6, 11.3**

- [x] 16. Checkpoint - Advanced features tamamlandı
  - Tüm advanced feature testlerinin geçtiğinden emin ol
  - Saved filters CRUD'u test et
  - Export functionality'yi test et
  - Filter history'yi test et
  - Kullanıcıya sorular varsa sor

### Phase 4: Performance & Polish

- [x] 17. Performance optimizations
  - [x] 17.1 Query result caching implementasyonu
    - FilterCacheService'i FilterService.apply_filters()'a entegre et
    - Cache key generation: hash(entity_type + filters + workspace_id)
    - Cache TTL: 5 minutes (300 seconds)
    - Cache invalidation: entity create/update/delete events
    - _Requirements: 6.4_
  
  - [x] 17.2 Preview count caching implementasyonu
    - GET /api/v1/filters/preview-count endpoint ekle
    - COUNT(*) query (full result set yükleme)
    - Cache TTL: 30 seconds
    - Debouncing: 300ms
    - "Calculating..." indicator
    - "No results" warning
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7_
  
  - [x] 17.3 Slow query monitoring
    - FilterExecutionLog'a slow query logging ekle
    - is_slow_query=true flag (execution_time_ms > 1000)
    - EXPLAIN query plan logging
    - GET /api/v1/admin/filter-stats endpoint ekle
    - Slow query statistics: total_queries, slow_queries, avg_execution_time
    - _Requirements: 6.3, 6.6, 17.1, 17.2, 17.3, 17.7_
  
  - [ ]* 17.4 Performance için property test yaz
    - **Property 16: Query Result Caching**
    - **Property 17: Slow Query Logging**
    - **Property 48: Live Preview Count Updates**
    - **Property 49: Preview Count Caching**
    - **Validates: Requirements 6.4, 6.6, 18.1, 18.7**

- [x] 18. Security hardening
  - [x] 18.1 Security validations ve checks
    - FilterValidationService'de tüm validation'ları doğrula
    - SQL injection prevention test et
    - Workspace isolation test et
    - Rate limiting test et
    - CSRF protection ekle (Flask-WTF)
    - XSS prevention (textContent kullan, innerHTML kullanma)
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_
  
  - [ ]* 18.2 Security için unit test yaz
    - Test SQL injection prevention
    - Test workspace isolation
    - Test unauthorized access (401)
    - Test cross-workspace access (403)
    - Test rate limiting (429)
    - **Validates: Requirements 15.1, 15.4, 15.5, 15.6, 15.7**

- [x] 19. UI polish ve animations
  - [x] 19.1 Loading states ve animations
    - FilterPanel'e loading states ekle (skeleton screens)
    - Filter chip fade-in/fade-out animations (200ms)
    - Panel collapse/expand animations (300ms)
    - Button hover effects ve active states
    - Progress indicators (export, preview count)
    - _Requirements: 1.3, 4.7, 7.7, 13.7_
  
  - [x] 19.2 Error messages ve empty states
    - User-friendly error messages (ERROR_MESSAGES mapping)
    - Empty state messages ("No results found", "No saved filters")
    - Validation error feedback (inline, real-time)
    - Toast notifications (success, error, warning)
    - _Requirements: 5.7, 18.4_

- [x] 20. Final testing ve bug fixes
  - [ ]* 20.1 Full integration test suite
    - End-to-end test: filter creation → application → results
    - End-to-end test: saved filter → load → edit → delete
    - End-to-end test: filter → export → download
    - Cross-browser testing (Chrome, Firefox, Safari, Edge)
    - Mobile device testing (iOS, Android)
  
  - [ ]* 20.2 Property test suite completion
    - Tüm 58 correctness property için property test yaz
    - Hypothesis configuration: minimum 100 iterations
    - Test coverage: backend minimum 80%, frontend minimum 70%
    - **Validates: All 58 correctness properties**
  
  - [x] 20.3 Bug fixes ve polish
    - Tüm test failures'ı düzelt
    - Edge case'leri handle et
    - Performance bottleneck'leri optimize et
    - Code review ve refactoring

- [x] 21. Final checkpoint - Production ready
  - Tüm testlerin geçtiğinden emin ol (unit + property + integration)
  - Performance metrics'i doğrula (query execution < 500ms)
  - Security checklist'i tamamla
  - Documentation'ı tamamla (API docs, user guide)
  - Kullanıcıya final onay sor

## Notes

- `*` ile işaretli task'lar optional test task'larıdır - MVP için skip edilebilir
- Her task spesifik requirement'lara referans verir (traceability)
- Checkpoint'ler incremental validation sağlar
- Property test'ler universal correctness property'leri doğrular
- Unit test'ler specific example'ları ve edge case'leri doğrular
- Migration gerekmez - tüm DB modelleri zaten mevcut (SavedFilter, UserDefinedFilter, FilterExecutionLog)
- Backend: Python/Flask, Frontend: JavaScript/Tailwind CSS
- Test framework: pytest (backend), Jest (frontend), Hypothesis (property tests)
