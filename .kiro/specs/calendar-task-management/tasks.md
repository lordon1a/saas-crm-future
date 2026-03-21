# Implementation Plan: Takvim ve Görev Yönetimi Sistemi

## Overview

Bu implementation plan, WhatsApp CRM SaaS uygulamasına kapsamlı Takvim ve Görev Yönetimi sistemini ekler. Sistem, mevcut Task modelini genişletir, zamanlı görevler oluşturur, takvim görünümü sağlar ve akıllı bildirim sistemi içerir. Tüm implementasyon Flask + PostgreSQL + gevent stack'i üzerinde, Render Free Plan (512MB RAM) için optimize edilmiştir.

## Tasks

- [x] 1. Database modelleri ve migration oluştur
  - [x] 1.1 Task modeline yeni kolonlar ekle (models_crm.py)
    - start_time, end_time, timezone, task_type, contact_id kolonlarını ekle
    - Yeni metodlar ekle: is_overdue(), duration_minutes(), to_calendar_event(), _get_color_by_type()
    - Yeni indeksler tanımla: idx_task_workspace_start_time, idx_task_workspace_status, idx_task_assignee_status, idx_task_type
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 21.1, 21.2, 21.3, 21.4, 22.1, 22.2, 22.3, 23.1, 23.2, 23.3, 23.4, 24.1, 24.2, 24.3, 24.4_

  - [x] 1.2 TaskNotification modelini oluştur (models_crm.py)
    - Tüm kolonları tanımla: workspace_id, task_id, user_id, notify_at, message, notification_type, is_sent, sent_at, is_read, read_at, created_at
    - Task ile relationship tanımla (cascade='all, delete-orphan')
    - İndeksler oluştur: idx_notification_pending, idx_notification_user_unread, idx_notification_workspace_user
    - Metodlar ekle: mark_as_sent(), mark_as_read()
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 11.5, 13.1, 13.2, 13.3, 13.4, 13.5, 14.1, 14.2, 14.3, 14.4, 16.1, 16.2, 16.3, 17.1, 17.2, 17.3, 17.4, 17.5_

  - [x] 1.3 NotificationPreference modelini oluştur (models_crm.py)
    - Tüm kolonları tanımla: workspace_id, user_id, task_reminder_enabled, task_overdue_enabled, task_assigned_enabled, task_updated_enabled, reminder_minutes_before, created_at, updated_at
    - Unique constraint ekle: (workspace_id, user_id)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 1.4 Migration script oluştur (migrations/add_calendar_task_features.py)
    - Task tablosuna yeni kolonlar ekleyen migration
    - TaskNotification tablosu oluşturan migration
    - NotificationPreference tablosu oluşturan migration
    - Tüm indeksleri oluşturan migration
    - _Requirements: 29.1, 29.2, 29.3, 29.4_

  - [x] 1.5 app.py run_migrations() fonksiyonunu güncelle
    - Task tablosuna calendar field'ları ekleyen SQL
    - task_notifications tablosu oluşturan SQL
    - notification_preferences tablosu oluşturan SQL
    - Tüm indeksleri oluşturan SQL
    - **RENDER FREE TIER İÇİN ZORUNLU - Production'da shell yok!**
    - _Requirements: 29.5_

- [x] 2. Checkpoint - Database migration'ı test et
  - Migration script'ini local'de çalıştır: `flask db migrate -m "Add calendar and task notification features"`
  - Migration'ı uygula: `flask db upgrade`
  - Tüm tabloların ve kolonların oluştuğunu doğrula
  - Kullanıcıya sor: Migration başarılı mı? Devam edilsin mi?

- [x] 3. Service layer implementasyonu
  - [x] 3.1 TaskService'i genişlet (services/task_service.py)
    - create_task() metodunu güncelle: zamanlı görev oluşturma, bildirim kayıtları oluşturma, activity log
    - update_task() metodunu güncelle: zaman değişikliği kontrolü, bildirim yenileme, activity log
    - _create_task_notifications() metodu ekle: kullanıcı tercihlerine göre bildirim oluşturma
    - get_tasks_for_calendar() metodu ekle: tarih aralığı ve filtrelerle görev getirme
    - mark_overdue_tasks() metodu ekle: süresi geçmiş görevleri işaretleme ve overdue bildirimi oluşturma
    - _create_activity_log() metodu ekle: activity log kaydı oluşturma
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 10.1, 10.2, 10.3, 10.4, 10.5, 19.1, 19.2, 19.3, 19.4, 20.1, 20.2, 20.3, 20.4, 26.1, 26.2, 26.3, 26.4_

  - [x] 3.2 NotificationService oluştur (services/notification_service.py)
    - send_pending_notifications() metodu: zamanı gelmiş bildirimleri Socket.IO ile gönderme
    - _emit_notification() metodu: Socket.IO emit işlemi
    - get_user_notifications() metodu: kullanıcı bildirimlerini getirme
    - get_unread_count() metodu: okunmamış bildirim sayısı
    - mark_as_read() metodu: tek bildirimi okundu işaretleme
    - mark_all_as_read() metodu: tüm bildirimleri okundu işaretleme
    - get_or_create_preferences() metodu: kullanıcı tercihlerini getir/oluştur
    - update_preferences() metodu: bildirim tercihlerini güncelle
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 12.1, 12.2, 12.3, 12.4, 13.1, 13.2, 13.3, 13.4, 13.5, 14.1, 14.2, 14.3, 14.4, 15.1, 15.2, 15.3, 15.4, 19.1, 19.2, 19.3, 19.4_

  - [x] 3.3 TaskScheduler oluştur (services/task_scheduler.py)
    - init_scheduler() metodu: APScheduler başlatma, gevent uyumlu
    - Her dakika çalışan job: send_pending_notifications
    - Her 5 dakikada çalışan job: check_overdue_tasks (tüm workspace'ler için)
    - shutdown() metodu: graceful shutdown
    - _send_notifications_job() ve _check_overdue_tasks_job() metodları
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 11.1, 11.2, 11.3, 11.4, 11.5, 18.5, 28.1, 28.2, 28.3, 28.4_

- [x] 4. Checkpoint - Service layer'ı test et
  - TaskService.create_task() ile zamanlı görev oluştur
  - Bildirim kayıtlarının oluştuğunu doğrula
  - NotificationService.get_user_notifications() ile bildirimleri getir
  - TaskScheduler'ın başladığını ve job'ların çalıştığını doğrula
  - Kullanıcıya sor: Service layer çalışıyor mu? Devam edilsin mi?

- [x] 5. API endpoints implementasyonu
  - [x] 5.1 Calendar endpoints oluştur (routes/calendar.py)
    - Blueprint oluştur: calendar_bp
    - GET /api/v1/calendar/events endpoint: tarih aralığı ve filtrelerle görevleri getir
    - @login_required decorator kullan
    - Tarih parametrelerini parse et ve validate et
    - TaskService.get_tasks_for_calendar() çağır
    - Hata yönetimi: try/except, rollback, logging
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 25.1, 25.2, 25.3, 25.4, 26.1, 26.2, 26.3, 26.4_

  - [x] 5.2 Task endpoints'i genişlet (routes/tasks.py)
    - POST /api/v1/tasks endpoint'ini güncelle: zamanlı görev oluşturma desteği
    - PATCH /api/v1/tasks/<id> endpoint'ini güncelle: sürükle-bırak için zaman güncelleme
    - POST /api/v1/tasks/<id>/complete endpoint ekle: görevi tamamlama
    - Tarih string'lerini datetime'a dönüştür
    - Hata yönetimi: try/except, rollback, logging
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 25.1, 25.2, 25.3, 25.4, 26.1, 26.2, 26.3, 26.4_

  - [x] 5.3 Notification endpoints oluştur (routes/notifications.py)
    - Blueprint oluştur: notifications_bp
    - GET /api/v1/notifications endpoint: kullanıcı bildirimlerini getir (unread_only, limit parametreleri)
    - POST /api/v1/notifications/<id>/read endpoint: bildirimi okundu işaretle
    - POST /api/v1/notifications/read-all endpoint: tüm bildirimleri okundu işaretle
    - GET /api/v1/notifications/preferences endpoint: bildirim tercihlerini getir
    - PATCH /api/v1/notifications/preferences endpoint: bildirim tercihlerini güncelle
    - @login_required decorator kullan
    - Hata yönetimi: try/except, rollback, logging
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 14.1, 14.2, 14.3, 14.4, 15.1, 15.2, 15.3, 15.4, 25.1, 25.2, 25.3, 25.4_

- [x] 6. app.py entegrasyonları
  - [x] 6.1 Blueprint'leri kaydet
    - calendar_bp'yi register et
    - notifications_bp'yi register et
    - _Requirements: 25.1_

  - [x] 6.2 TaskScheduler'ı başlat
    - TaskScheduler.init_scheduler(app) çağır
    - atexit.register ile graceful shutdown ekle
    - _Requirements: 28.1, 28.2, 28.3, 28.4_

- [ ] 7. Checkpoint - API endpoints'leri test et
  - Postman/curl ile tüm endpoint'leri test et
  - Calendar events endpoint'ini test et
  - Task oluşturma/güncelleme endpoint'lerini test et
  - Notification endpoint'lerini test et
  - Background scheduler'ın çalıştığını doğrula
  - Kullanıcıya sor: API'ler çalışıyor mu? Devam edilsin mi?

- [x] 8. Frontend - Takvim görünümü
  - [x] 8.1 CalendarView class oluştur (static/calendar.js)
    - Constructor: containerId, currentView, currentDate, events, filters
    - init() metodu: render, event listeners, loadEvents
    - render() metodu: takvim HTML'ini oluştur
    - generateMonthView(), generateWeekView(), generateDayView(), generateAgendaView() metodları
    - loadEvents() metodu: API'den görevleri getir
    - renderEvents() metodu: event'leri takvime yerleştir
    - createEventElement() metodu: event HTML elementi oluştur
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 8.2 Sürükle-bırak işlevselliği ekle (static/calendar.js)
    - attachEventHandlers() metodu: drag, click, resize event'leri
    - onDragStart(), onDragEnd() metodları
    - calculateNewDateTime() metodu: yeni tarih/saat hesaplama
    - updateEventTime() metodu: backend'e PATCH isteği gönder
    - onEventClick() metodu: task modal'ını aç
    - onEmptySlotClick() metodu: yeni görev modal'ını aç
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 8.3 Filtreleme ve görünüm değiştirme (static/calendar.js)
    - changeView() metodu: month/week/day/agenda arası geçiş
    - applyFilter() metodu: task_type, assignee_id, status filtreleri
    - getTypeIcon() metodu: görev tipine göre icon
    - escapeHtml() metodu: XSS koruması
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 4.1, 4.2, 4.3, 4.4, 4.5, 27.1, 27.2, 27.3_

- [x] 9. Frontend - Görev modalı
  - [x] 9.1 TaskModal class oluştur (static/task-modal.js)
    - Constructor: modal, taskId, mode (create/edit)
    - init() metodu: modal HTML oluştur, event listeners
    - open() metodu: modal'ı aç (edit mode)
    - openNew() metodu: modal'ı aç (create mode, varsayılan değerlerle)
    - loadTask() metodu: mevcut görevi yükle ve formu doldur
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 9.2 Form validasyonu ve kaydetme (static/task-modal.js)
    - save() metodu: form validasyonu, POST/PATCH isteği
    - validateForm() metodu: başlık, tarih aralığı kontrolü
    - getFormData() metodu: form verilerini topla
    - close() metodu: modal'ı kapat ve formu sıfırla
    - formatDateTimeLocal() metodu: datetime-local input formatı
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 26.1, 26.2, 26.3, 26.4_

- [x] 10. Frontend - Bildirim zili
  - [x] 10.1 NotificationBell class oluştur (static/notification-bell.js)
    - Constructor: bellIcon, badge, dropdown, unreadCount, socket
    - init() metodu: bell HTML oluştur, event listeners, Socket.IO bağlantısı
    - createBellHTML() metodu: bildirim zili UI
    - connectSocket() metodu: Socket.IO bağlantısı, user room'una katıl
    - onNewNotification() metodu: yeni bildirim geldiğinde çalışır
    - playNotificationSound() metodu: bildirim sesi çal
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 30.1, 30.2, 30.3_

  - [x] 10.2 Bildirim dropdown ve işlemler (static/notification-bell.js)
    - toggleDropdown() metodu: dropdown aç/kapat
    - loadNotifications() metodu: API'den bildirimleri getir
    - renderNotifications() metodu: bildirimleri listele
    - createNotificationItem() metodu: bildirim item HTML
    - onNotificationClick() metodu: bildirime tıklandığında
    - markAsRead() metodu: tek bildirimi okundu işaretle
    - markAllAsRead() metodu: tüm bildirimleri okundu işaretle
    - updateBadge() metodu: okunmamış sayı rozetini güncelle
    - getNotificationIcon() metodu: bildirim tipine göre icon
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 14.1, 14.2, 14.3, 14.4, 15.1, 15.2, 15.3, 15.4_

- [x] 11. Frontend - HTML template
  - [x] 11.1 Calendar sayfası oluştur veya mevcut tasks.html'i genişlet
    - Takvim container div'i ekle
    - Görünüm değiştirme butonları (month/week/day/agenda)
    - Filtre dropdown'ları (task_type, assignee, status)
    - Yeni görev butonu
    - Bildirim zili component'i ekle
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 11.2 Task modal HTML ekle
    - Modal overlay ve container
    - Form alanları: title, description, start_time, end_time, task_type, priority, assignee, contact, company, deal
    - Kaydet ve iptal butonları
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 11.3 Script tag'leri ekle
    - calendar.js
    - task-modal.js
    - notification-bell.js
    - Initialization script'leri
    - _Requirements: 4.1, 12.1_

- [ ] 12. Checkpoint - Frontend'i test et
  - Takvim görünümünün render olduğunu doğrula
  - Görev oluşturma modal'ının açıldığını doğrula
  - Sürükle-bırak işlevinin çalıştığını doğrula
  - Bildirim zili ve dropdown'ın çalıştığını doğrula
  - Real-time bildirim geldiğinde UI'ın güncellendiğini doğrula
  - Kullanıcıya sor: Frontend çalışıyor mu? Devam edilsin mi?

- [x] 13. Performans optimizasyonu ve güvenlik
  - [x] 13.1 Database query optimizasyonu
    - TaskService.get_tasks_for_calendar()'da eager loading ekle (joinedload)
    - Background job'larda batch processing kullan
    - Index'lerin doğru kullanıldığını doğrula
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

  - [x] 13.2 Güvenlik kontrolleri
    - Tüm endpoint'lerde workspace_id kontrolü yap
    - Input validasyonu ekle (tarih formatı, boş değerler)
    - Frontend'de XSS koruması (escapeHtml)
    - SQL injection koruması (SQLAlchemy ORM kullanımı)
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 25.1, 25.2, 25.3, 25.4, 26.1, 26.2, 26.3, 26.4, 27.1, 27.2, 27.3_

  - [x] 13.3 Hata yönetimi
    - Tüm db.session.commit() çağrılarında try/except ekle
    - Background job'larda hata durumunda diğer job'ların çalışmaya devam etmesini sağla
    - Frontend'de API hata durumlarını handle et
    - Logging ekle (logger.error)
    - _Requirements: 19.1, 19.2, 19.3, 19.4_

- [x] 14. Final test ve deployment hazırlığı
  - [x] 14.1 End-to-end test senaryoları
    - Zamanlı görev oluştur ve takvimde görüntüle
    - Görevi sürükle-bırak ile taşı
    - Görev zamanı yaklaşınca bildirim al
    - Süresi geçmiş görevin otomatik overdue olmasını doğrula
    - Bildirim tercihlerini değiştir ve etkisini gör
    - _Requirements: Tüm gereksinimler_

  - [x] 14.2 Migration kontrolü
    - Migration script'inin production'da çalışacağını doğrula
    - app.py run_migrations() fonksiyonunun güncel olduğunu doğrula
    - Render'da deploy öncesi local'de son test
    - _Requirements: 29.1, 29.2, 29.3, 29.4, 29.5_

  - [x] 14.3 Documentation
    - API endpoint'lerini dokümante et
    - Kullanıcı için kısa kullanım kılavuzu hazırla (opsiyonel)
    - Code comment'leri kontrol et
    - _Requirements: Tüm gereksinimler_

- [ ] 15. Final checkpoint - Production'a hazır mı?
  - Tüm testler geçiyor mu?
  - Migration script hazır mı?
  - Background scheduler çalışıyor mu?
  - Socket.IO bildirimleri çalışıyor mu?
  - Performans kabul edilebilir mi (Render Free Plan)?
  - Kullanıcıya sor: Production'a deploy edilsin mi?

## Notes

- Her checkpoint task'ında kullanıcıdan onay alınmalı
- Migration işlemleri kritik - production'da shell olmadığı için app.py run_migrations() ZORUNLU
- Background scheduler gevent uyumlu olmalı (APScheduler)
- Socket.IO async_mode='gevent' olmalı
- Tüm endpoint'lerde @login_required ve workspace_id kontrolü zorunlu
- XSS koruması için frontend'de escapeHtml() kullanılmalı
- Database işlemlerinde try/except ve rollback zorunlu
- Render Free Plan (512MB RAM) için optimize edilmiş: batch processing, limit, eager loading
- Test-related sub-tasks yok (hepsi core implementation)
