# Requirements Document

## Introduction

Bu doküman, WhatsApp CRM SaaS uygulamasının Contacts ve Companies sayfalarındaki mevcut filter sisteminin tamamen yenilenmesi için gereksinimleri tanımlar. Mevcut sistem modern bir CRM seviyesinde değil, responsive tasarım eksik, işlevsel sorunlar var (starred filter çalışmıyor) ve backend'de filtreler birbirleriyle çakışıyor. Bu yenileme ile sistem hem UI/UX hem de backend açısından tamamen modernize edilecektir.

## Glossary

- **Filter_System**: Contacts ve Companies sayfalarında kullanıcıların veri filtrelemesini sağlayan yenilenmiş sistem bileşeni
- **Filter_Panel**: Modern, responsive, collapsible filtre arayüzü bileşeni
- **Filter_Chip**: Aktif filtreleri gösteren, kaldırılabilir modern badge/chip bileşeni
- **Quick_Filter**: Önceden tanımlanmış, tek tıkla uygulanabilen hızlı filtre seçeneği
- **Saved_Filter**: Kullanıcı tarafından kaydedilmiş, tekrar kullanılabilir filtre konfigürasyonu
- **Filter_Operator**: Filtreleme kriterlerinin nasıl karşılaştırılacağını belirleyen operatör
- **Filter_State**: Aktif filtrelerin durumu ve konfigürasyonu
- **Contact**: CRM sistemindeki kişi kaydı
- **Company**: CRM sistemindeki şirket kaydı
- **Workspace**: Multi-tenant sistemde tenant izolasyon birimi
- **Filter_Backend**: Filtreleme işlemlerini gerçekleştiren backend servis katmanı
- **Filter_Conflict**: Birden fazla filtrenin birbirleriyle çakışması durumu

## Requirements

### Requirement 1: Modern Responsive UI Tasarımı

**User Story:** As a CRM user, I want a modern, responsive filter interface that works seamlessly on all devices, so that I can filter data efficiently from desktop, tablet, or mobile.

#### Acceptance Criteria

1. THE Filter_Panel SHALL be fully responsive and adapt to screen sizes: desktop (>1024px), tablet (768-1024px), mobile (<768px)
2. THE Filter_Panel SHALL use modern design patterns with proper spacing, shadows, and visual hierarchy
3. THE Filter_Panel SHALL be collapsible with smooth animations (300ms transition)
4. THE Filter_Panel SHALL display as a sidebar on desktop and as a bottom sheet on mobile
5. THE Filter_Panel SHALL use Tailwind CSS utility classes for consistent styling
6. THE Filter_UI SHALL follow modern CRM design standards (similar to Pipedrive, HubSpot, Salesforce)
7. THE Filter_Panel SHALL support touch gestures on mobile devices (swipe to close, tap to expand)
8. THE Filter_Panel SHALL maintain state when switching between collapsed and expanded views

### Requirement 2: Starred Filter Düzeltmesi

**User Story:** As a CRM user, I want the starred filter to work correctly, so that I can quickly access my favorite contacts.

#### Acceptance Criteria

1. WHEN a user clicks the "Starred" quick filter, THE Filter_System SHALL return only contacts where is_starred=true
2. THE Filter_System SHALL use proper database indexing on is_starred column for performance
3. THE Filter_UI SHALL visually indicate when starred filter is active with a highlighted chip
4. WHEN a user toggles a contact's starred status, THE Filter_System SHALL immediately update the filtered results if starred filter is active
5. THE Filter_System SHALL persist starred filter state in session storage
6. THE Filter_Backend SHALL use parameterized queries to prevent SQL injection on starred filter

### Requirement 3: Backend Filter Çakışma Çözümü

**User Story:** As a CRM user, I want filters to work together correctly without conflicts, so that I get accurate results when combining multiple criteria.

#### Acceptance Criteria

1. THE Filter_Backend SHALL apply all active filters with AND logic without conflicts
2. THE Filter_Backend SHALL validate filter combinations before execution to detect conflicts
3. IF a Filter_Conflict is detected, THEN THE Filter_System SHALL return a clear error message to the user
4. THE Filter_Backend SHALL use a single unified query builder that prevents duplicate WHERE clauses
5. THE Filter_Backend SHALL log all filter operations with applied criteria for debugging
6. THE Filter_Backend SHALL handle null values correctly in filter comparisons
7. THE Filter_Backend SHALL properly escape and sanitize all filter values to prevent injection attacks

### Requirement 4: Modern Filter Chip Tasarımı

**User Story:** As a CRM user, I want to see active filters as modern chips/badges, so that I can easily understand and manage my current filter state.

#### Acceptance Criteria

1. THE Filter_UI SHALL display each active filter as a Filter_Chip with field name, operator, and value
2. THE Filter_Chip SHALL have a close button (×) to remove individual filters
3. THE Filter_Chip SHALL use modern styling with rounded corners, subtle shadows, and hover effects
4. THE Filter_Chip SHALL display different colors based on filter type (text: blue, number: green, date: purple, boolean: orange)
5. THE Filter_UI SHALL display Filter_Chips in a flex-wrap container that adapts to available space
6. WHEN a user hovers over a Filter_Chip, THE Filter_UI SHALL show a tooltip with full filter details
7. THE Filter_UI SHALL animate Filter_Chip addition and removal with fade-in/fade-out effects (200ms)

### Requirement 5: Gelişmiş Arama Fonksiyonalitesi

**User Story:** As a CRM user, I want a powerful global search that searches across all relevant fields, so that I can quickly find any contact or company.

#### Acceptance Criteria

1. THE Filter_System SHALL provide a global search input with debouncing (300ms delay)
2. THE Filter_System SHALL search across multiple fields for Contacts: first_name, last_name, email, phone, whatsapp_phone, job_title, company_name
3. THE Filter_System SHALL search across multiple fields for Companies: name, industry, website, phone, address
4. THE Filter_System SHALL use case-insensitive ILIKE queries for text search
5. THE Filter_System SHALL highlight matching text in search results (frontend)
6. THE Filter_System SHALL display search suggestions as user types (minimum 2 characters)
7. THE Filter_System SHALL show "No results found" message when search returns empty results
8. THE Filter_System SHALL clear search when user clicks clear button (×) in search input

### Requirement 6: Filtre Performans Optimizasyonu

**User Story:** As a system administrator, I want filters to execute quickly even with large datasets, so that users have a smooth experience.

#### Acceptance Criteria

1. THE Filter_Backend SHALL execute filter queries in under 500ms for datasets up to 10,000 records
2. THE Filter_Backend SHALL use database indexes on all filterable columns: workspace_id, is_deleted, is_starred, role, lead_score, industry, size, created_at, updated_at
3. THE Filter_Backend SHALL use query optimization techniques (EXPLAIN ANALYZE) to identify slow queries
4. THE Filter_Backend SHALL implement query result caching with 5-minute TTL for frequently used filters
5. THE Filter_Backend SHALL use connection pooling (pool_size=2) to manage database connections efficiently
6. THE Filter_Backend SHALL log slow queries (>1000ms) to filter_execution_logs table for monitoring
7. THE Filter_Backend SHALL limit concurrent filter requests per user to 3 to prevent resource exhaustion

### Requirement 7: Modern Quick Filter Tasarımı

**User Story:** As a CRM user, I want visually appealing quick filter buttons, so that I can quickly apply common filters with one click.

#### Acceptance Criteria

1. THE Filter_UI SHALL display Quick_Filter buttons with icons and labels
2. THE Quick_Filter buttons SHALL use modern styling with hover effects and active states
3. THE Quick_Filter buttons SHALL show a count badge indicating how many records match the filter
4. WHEN a Quick_Filter is active, THE Filter_UI SHALL highlight the button with a distinct color and border
5. THE Filter_UI SHALL display Quick_Filters in a horizontal scrollable container on mobile
6. THE Filter_UI SHALL support keyboard navigation (Tab, Enter) for Quick_Filter buttons
7. THE Quick_Filter buttons SHALL have loading states while filter is being applied

### Requirement 8: Filtre Durumu Yönetimi

**User Story:** As a CRM user, I want my filter settings to persist across sessions, so that I don't lose my work when I navigate away or refresh the page.

#### Acceptance Criteria

1. THE Filter_System SHALL save active Filter_State to browser localStorage
2. WHEN a user returns to Contacts or Companies page, THE Filter_System SHALL restore the previous Filter_State from localStorage
3. THE Filter_System SHALL encode Filter_State in URL query parameters for shareable links
4. WHEN a user shares a filtered URL, THE Filter_System SHALL apply filters from URL parameters on page load
5. THE Filter_System SHALL validate URL parameters to prevent injection attacks
6. THE Filter_System SHALL clear Filter_State from localStorage when user clicks "Clear All Filters"
7. THE Filter_System SHALL sync Filter_State across multiple browser tabs using localStorage events

### Requirement 9: Tarih Aralığı Filtreleme İyileştirmesi

**User Story:** As a CRM user, I want an intuitive date range picker, so that I can easily filter records by date ranges.

#### Acceptance Criteria

1. THE Filter_UI SHALL provide a modern date range picker with calendar view
2. THE Filter_UI SHALL support preset date ranges: "Today", "Yesterday", "Last 7 Days", "Last 30 Days", "This Month", "Last Month", "This Year", "Custom Range"
3. WHEN a user selects a preset date range, THE Filter_System SHALL calculate the appropriate start and end dates
4. THE Filter_UI SHALL display selected date range in human-readable format (e.g., "Jan 1, 2024 - Jan 31, 2024")
5. THE Filter_System SHALL handle timezone conversion using workspace timezone settings
6. THE Filter_UI SHALL validate that start date is before or equal to end date
7. THE Filter_UI SHALL highlight today's date in the calendar picker

### Requirement 10: Sayısal Filtre İyileştirmesi

**User Story:** As a CRM user, I want an intuitive way to filter by numeric ranges, so that I can segment data by lead score or other numeric fields.

#### Acceptance Criteria

1. THE Filter_UI SHALL provide a dual-handle range slider for lead_score field (0-100)
2. THE Filter_UI SHALL display current min and max values above the slider handles
3. THE Filter_UI SHALL allow users to type exact values in numeric input fields
4. WHEN a user adjusts the slider, THE Filter_UI SHALL update the numeric inputs in real-time
5. WHEN a user types in numeric inputs, THE Filter_UI SHALL update the slider position
6. THE Filter_System SHALL validate that minimum value is less than or equal to maximum value
7. THE Filter_UI SHALL show a visual indicator of the selected range on the slider track

### Requirement 11: Çoklu Seçim Filtre İyileştirmesi

**User Story:** As a CRM user, I want a modern multi-select dropdown for categorical fields, so that I can easily select multiple values.

#### Acceptance Criteria

1. THE Filter_UI SHALL provide a searchable multi-select dropdown for fields: role, industry, size
2. THE Filter_UI SHALL display selected values as chips inside the dropdown
3. THE Filter_UI SHALL support keyboard navigation (Arrow keys, Enter, Escape) in the dropdown
4. THE Filter_UI SHALL show a "Select All" and "Clear All" option at the top of the dropdown
5. THE Filter_UI SHALL display a count of selected items in the dropdown trigger button
6. THE Filter_UI SHALL close the dropdown when user clicks outside or presses Escape
7. THE Filter_UI SHALL highlight matching options as user types in the search box

### Requirement 12: Kaydedilmiş Filtreler İyileştirmesi

**User Story:** As a CRM user, I want to easily save and manage my frequently used filters, so that I can reuse them without reconfiguring.

#### Acceptance Criteria

1. WHEN a user has active filters, THE Filter_UI SHALL display a "Save Filter" button in the filter panel
2. WHEN a user clicks "Save Filter", THE Filter_UI SHALL open a modal with name and description inputs
3. THE Filter_System SHALL store Saved_Filter with: name, description, entity_type, filter_config (JSON), workspace_id, user_id, is_shared, created_at
4. THE Filter_UI SHALL display saved filters in a dropdown with search functionality
5. THE Filter_UI SHALL show filter metadata (name, description, created date, creator name) on hover
6. THE Filter_UI SHALL allow users to edit saved filter name and description
7. THE Filter_UI SHALL allow users to delete their own saved filters with confirmation dialog
8. THE Filter_System SHALL limit each user to maximum 50 Saved_Filter items per entity type

### Requirement 13: Filtre Dışa Aktarma İyileştirmesi

**User Story:** As a CRM user, I want to export filtered results with a modern interface, so that I can use the data in external tools.

#### Acceptance Criteria

1. WHEN a user has active filters, THE Filter_UI SHALL display an "Export" button with a dropdown menu
2. THE Filter_UI SHALL offer export formats: CSV, Excel (XLSX), PDF (optional)
3. WHEN a user selects an export format, THE Filter_UI SHALL show a column selection modal
4. THE Filter_UI SHALL allow users to select which columns to include in the export
5. THE Filter_System SHALL generate the export file with all filtered records (not just current page)
6. THE Filter_System SHALL limit export to maximum 10,000 records per request
7. THE Filter_System SHALL show a progress indicator during export generation
8. THE Filter_System SHALL download the file with a descriptive filename (e.g., "contacts_filtered_2024-01-15.csv")

### Requirement 14: Mobil Responsive Filtre Deneyimi

**User Story:** As a mobile CRM user, I want a touch-friendly filter interface, so that I can filter data efficiently on my phone or tablet.

#### Acceptance Criteria

1. THE Filter_Panel SHALL display as a bottom sheet on mobile devices (<768px)
2. THE Filter_Panel SHALL support swipe-down gesture to close on mobile
3. THE Filter_UI SHALL use larger touch targets (minimum 44x44px) for all interactive elements on mobile
4. THE Filter_UI SHALL display Quick_Filters in a horizontal scrollable container on mobile
5. THE Filter_UI SHALL stack filter controls vertically on mobile for better usability
6. THE Filter_UI SHALL use native mobile date pickers when available
7. THE Filter_Panel SHALL occupy maximum 80% of screen height on mobile to allow viewing results

### Requirement 15: Filtre Güvenliği ve Validasyon

**User Story:** As a security administrator, I want all filter operations to be secure and validated, so that the system is protected from attacks.

#### Acceptance Criteria

1. THE Filter_Backend SHALL enforce workspace_id isolation for all filter queries
2. THE Filter_Backend SHALL require @login_required decorator on all filter endpoints
3. THE Filter_Backend SHALL validate that user's workspace_id matches the filtered data's workspace_id
4. THE Filter_Backend SHALL sanitize all user inputs to prevent SQL injection
5. THE Filter_Backend SHALL use parameterized queries for all database operations
6. THE Filter_Backend SHALL validate filter operator and value types before execution
7. IF a user attempts to access another workspace's data, THEN THE Filter_Backend SHALL return 403 Forbidden and log the attempt

### Requirement 16: Filtre API Endpoint'leri Yenilenmesi

**User Story:** As a developer, I want clean, well-documented filter API endpoints, so that I can integrate filtering into other parts of the application.

#### Acceptance Criteria

1. THE Filter_Backend SHALL provide GET /api/v1/contacts endpoint with query parameters: filters (JSON), page, per_page, sort_by, sort_order
2. THE Filter_Backend SHALL provide GET /api/v1/companies endpoint with same query parameters
3. THE Filter_Backend SHALL return standardized JSON responses with contacts/companies array and pagination object
4. THE Filter_Backend SHALL return 400 Bad Request with descriptive error messages for invalid filter parameters
5. THE Filter_Backend SHALL return 401 Unauthorized if user is not authenticated
6. THE Filter_Backend SHALL return 403 Forbidden if user attempts to access data outside their workspace
7. THE Filter_Backend SHALL include applied_filters object in response for debugging

### Requirement 17: Filtre Performans İzleme

**User Story:** As a system administrator, I want to monitor filter performance, so that I can identify and fix slow queries.

#### Acceptance Criteria

1. THE Filter_Backend SHALL log all filter operations to filter_execution_logs table
2. THE Filter_Backend SHALL record: workspace_id, user_id, entity_type, filter_config, result_count, execution_time_ms, created_at
3. THE Filter_Backend SHALL flag queries as slow_query if execution_time_ms > 1000
4. THE Filter_Backend SHALL provide an admin endpoint to view slow query statistics
5. THE Filter_Backend SHALL send alerts when slow query rate exceeds 10% of total queries
6. THE Filter_Backend SHALL automatically add missing indexes when slow queries are detected on specific columns
7. THE Filter_Backend SHALL provide query execution plans (EXPLAIN) for slow queries in logs

### Requirement 18: Filtre Önizleme

**User Story:** As a CRM user, I want to preview filter results before applying them, so that I can verify my filter configuration is correct.

#### Acceptance Criteria

1. WHEN a user configures a filter, THE Filter_UI SHALL show a live count of matching records
2. THE Filter_UI SHALL update the count in real-time as user modifies filter criteria (with debouncing)
3. THE Filter_UI SHALL display "Calculating..." indicator while count is being fetched
4. THE Filter_UI SHALL show "No results" warning if filter would return zero records
5. THE Filter_UI SHALL allow users to apply filter even if count is zero (user may want to verify)
6. THE Filter_Backend SHALL use COUNT(*) query for preview to avoid loading full result set
7. THE Filter_Backend SHALL cache preview counts for 30 seconds to reduce database load

### Requirement 19: Filtre Geçmişi

**User Story:** As a CRM user, I want to see my recent filter history, so that I can quickly reapply filters I used recently.

#### Acceptance Criteria

1. THE Filter_System SHALL store the last 10 filter configurations per user in localStorage
2. THE Filter_UI SHALL display a "Recent Filters" dropdown in the filter panel
3. THE Filter_UI SHALL show filter name (if saved) or auto-generated description for recent filters
4. WHEN a user selects a recent filter, THE Filter_System SHALL apply it immediately
5. THE Filter_UI SHALL display timestamp of when each recent filter was last used
6. THE Filter_UI SHALL allow users to clear their filter history
7. THE Filter_System SHALL remove duplicate filters from history (keep most recent)

### Requirement 20: Filtre Paylaşımı

**User Story:** As a CRM user, I want to share my filters with team members, so that we can collaborate using the same data views.

#### Acceptance Criteria

1. WHEN a user saves a filter, THE Filter_UI SHALL provide a "Share with team" checkbox
2. WHEN a filter is shared, THE Filter_System SHALL set is_shared=true and make it visible to all workspace users
3. THE Filter_UI SHALL display shared filters in a separate "Team Filters" section
4. THE Filter_UI SHALL show the creator's name and creation date for shared filters
5. THE Filter_System SHALL allow only the creator to edit or delete shared filters
6. THE Filter_UI SHALL allow other users to duplicate shared filters to their own saved filters
7. THE Filter_System SHALL send notifications to team members when a new filter is shared

