# Takvim ve Görev Yönetimi Sistemi - Gereksinimler Belgesi

## Giriş

Bu belge, WhatsApp CRM SaaS uygulamasına eklenecek Takvim ve Görev Yönetimi sisteminin fonksiyonel gereksinimlerini tanımlar. Sistem, kullanıcıların görevleri zamanlı olarak oluşturmasını, takvim görünümünde görselleştirmesini ve otomatik bildirimler almasını sağlayacaktır.

## Sözlük

- **System**: Takvim ve Görev Yönetimi Sistemi
- **Task**: Zamanlı veya zamansız görev kaydı
- **Calendar_View**: Takvim görünüm bileşeni (aylık, haftalık, günlük, ajanda)
- **Notification_Service**: Bildirim yönetim servisi
- **Task_Service**: Görev yönetim servisi
- **Background_Scheduler**: Arka plan görev zamanlayıcı
- **User**: Sistemi kullanan kullanıcı
- **Workspace**: Multi-tenant izolasyon birimi
- **Task_Type**: Görev kategorisi (call, meeting, email, todo, follow_up, other)
- **Task_Status**: Görev durumu (pending, completed, cancelled, overdue)
- **Notification_Preference**: Kullanıcı bildirim tercihleri
- **Task_Notification**: Bildirim kaydı

## Gereksinimler

### Gereksinim 1: Zamanlı Görev Oluşturma

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, belirli bir tarih ve saatte başlayıp biten görevler oluşturmak istiyorum, böylece zamanımı daha iyi planlayabilirim.

#### Kabul Kriterleri

1. WHEN bir kullanıcı görev oluşturur, THE System SHALL başlangıç zamanı, bitiş zamanı ve timezone bilgilerini kaydetmeli
2. WHEN başlangıç zamanı bitiş zamanından sonra ise, THE System SHALL hata döndürmeli ve görev oluşturmamalı
3. WHEN görev başlığı boş ise, THE System SHALL hata döndürmeli ve görev oluşturmamalı
4. THE System SHALL görev oluşturulduğunda workspace_id ile izole edilmiş kayıt oluşturmalı
5. WHEN görev oluşturulduğunda, THE System SHALL activity log kaydı oluşturmalı

### Gereksinim 2: Görev Kategorizasyonu

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, görevlerimi tipine göre kategorize etmek istiyorum, böylece farklı görev türlerini kolayca ayırt edebilirim.

#### Kabul Kriterleri

1. THE System SHALL görev tipi olarak call, meeting, email, todo, follow_up, other değerlerini desteklemeli
2. WHEN görev oluşturulurken tip belirtilmezse, THE System SHALL varsayılan olarak 'task' tipini atamalı
3. THE System SHALL her görev tipine farklı renk kodu atamalı
4. WHEN takvimde görevler görüntülendiğinde, THE System SHALL görev tipine göre renk kodlaması yapmalı

### Gereksinim 3: Görev İlişkilendirme

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, görevlerimi contact, company ve deal kayıtlarıyla ilişkilendirmek istiyorum, böylece bağlamsal bilgiye hızlıca erişebilirim.

#### Kabul Kriterleri

1. THE System SHALL görevlerin contact_id ile ilişkilendirilmesini desteklemeli
2. THE System SHALL görevlerin company_id ile ilişkilendirilmesini desteklemeli
3. THE System SHALL görevlerin deal_id ile ilişkilendirilmesini desteklemeli
4. WHEN ilişkili kayıt silindiğinde, THE System SHALL görevdeki foreign key'i NULL yapmalı (SET NULL)

### Gereksinim 4: Takvim Görünümleri

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, görevlerimi farklı takvim görünümlerinde görmek istiyorum, böylece ihtiyacıma göre en uygun görünümü seçebilirim.

#### Kabul Kriterleri

1. THE System SHALL aylık takvim görünümü sağlamalı
2. THE System SHALL haftalık takvim görünümü sağlamalı
3. THE System SHALL günlük takvim görünümü sağlamalı
4. THE System SHALL ajanda (liste) görünümü sağlamalı
5. WHEN kullanıcı görünüm değiştirdiğinde, THE System SHALL seçilen tarih aralığındaki görevleri yeniden yüklemeli

### Gereksinim 5: Takvim Event Getirme

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, belirli bir tarih aralığındaki görevleri takvimde görmek istiyorum, böylece planımı görselleştirebilirim.

#### Kabul Kriterleri

1. WHEN kullanıcı takvim görünümünü açtığında, THE System SHALL belirtilen tarih aralığındaki görevleri getirmeli
2. THE System SHALL sadece start_time değeri NULL olmayan görevleri takvimde göstermeli
3. THE System SHALL görevleri workspace_id ile filtrelemeli
4. WHEN kullanıcı filtre uyguladığında, THE System SHALL task_type, assignee_id ve status filtrelerini desteklemeli
5. THE System SHALL görevleri start_time'a göre artan sırada döndürmeli

### Gereksinim 6: Sürükle-Bırak ile Görev Güncelleme

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, takvimde görevleri sürükleyip bırakarak zamanını değiştirmek istiyorum, böylece hızlı düzenleme yapabilirim.

#### Kabul Kriterleri

1. WHEN kullanıcı takvimde bir görevi sürükleyip bıraktığında, THE System SHALL görevin start_time ve end_time değerlerini güncelleme
2. THE System SHALL görev süresini koruyarak yeni zamanları hesaplamalı
3. WHEN görev zamanı değiştiğinde, THE System SHALL henüz gönderilmemiş bildirimleri silmeli
4. WHEN görev zamanı değiştiğinde, THE System SHALL yeni bildirim kayıtları oluşturmalı
5. WHEN görev güncellendiğinde, THE System SHALL activity log kaydı oluşturmalı

### Gereksinim 7: Görev Durumu Yönetimi

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, görevlerimin durumunu takip etmek istiyorum, böylece hangi görevlerin tamamlandığını veya geciktiğini görebilirim.

#### Kabul Kriterleri

1. THE System SHALL pending, completed, cancelled, overdue durum değerlerini desteklemeli
2. WHEN görev tamamlandığında, THE System SHALL completed_at timestamp'ini kaydetmeli
3. WHEN görev durumu completed'a değiştiğinde, THE System SHALL is_overdue kontrolünü FALSE döndürmeli
4. WHEN görev durumu cancelled'a değiştiğinde, THE System SHALL is_overdue kontrolünü FALSE döndürmeli

### Gereksinim 8: Otomatik Overdue İşaretleme

**Kullanıcı Hikayesi:** Bir sistem yöneticisi olarak, süresi geçmiş görevlerin otomatik olarak işaretlenmesini istiyorum, böylece manuel kontrol gerekmez.

#### Kabul Kriterleri

1. THE Background_Scheduler SHALL her 5 dakikada bir süresi geçmiş görevleri kontrol etmeli
2. WHEN bir görevin end_time geçmiş ve status pending ise, THE System SHALL status'ü overdue olarak güncelleme
3. WHEN görev overdue olarak işaretlendiğinde, THE System SHALL overdue bildirimi oluşturmalı
4. THE System SHALL overdue kontrolünü workspace bazında yapmalı

### Gereksinim 9: Bildirim Tercihleri

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, hangi tür bildirimleri almak istediğimi ayarlamak istiyorum, böylece gereksiz bildirimlerden kaçınabilirim.

#### Kabul Kriterleri

1. THE System SHALL kullanıcı başına bildirim tercihleri kaydetmeli
2. THE System SHALL task_reminder_enabled, task_overdue_enabled, task_assigned_enabled, task_updated_enabled tercihlerini desteklemeli
3. THE System SHALL reminder_minutes_before değerini kaydetmeli (0, 5, 10, 15, 30, 60, 120, 1440 dakika)
4. WHEN kullanıcı tercihleri güncellendiğinde, THE System SHALL updated_at timestamp'ini güncelleme
5. WHEN kullanıcı için tercih kaydı yoksa, THE System SHALL varsayılan tercihleri oluşturmalı

### Gereksinim 10: Görev Hatırlatma Bildirimleri

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, görev zamanı yaklaşınca bildirim almak istiyorum, böylece görevimi kaçırmam.

#### Kabul Kriterleri

1. WHEN zamanlı görev oluşturulduğunda ve assignee_id atanmışsa, THE System SHALL bildirim kaydı oluşturmalı
2. THE System SHALL bildirim zamanını start_time - reminder_minutes_before olarak hesaplamalı
3. WHEN hesaplanan bildirim zamanı geçmişte ise, THE System SHALL bildirim kaydı oluşturmamalı
4. THE System SHALL bildirim kaydını is_sent=FALSE olarak oluşturmalı
5. WHEN kullanıcının task_reminder_enabled=FALSE ise, THE System SHALL hatırlatma bildirimi oluşturmamalı

### Gereksinim 11: Bildirim Gönderme

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, zamanı gelmiş bildirimleri otomatik olarak almak istiyorum, böylece görevlerimi takip edebilirim.

#### Kabul Kriterleri

1. THE Background_Scheduler SHALL her dakika bekleyen bildirimleri kontrol etmeli
2. WHEN bir bildirimin notify_at zamanı gelmiş ve is_sent=FALSE ise, THE System SHALL bildirimi Socket.IO ile gönderme
3. WHEN bildirim gönderildiğinde, THE System SHALL is_sent=TRUE ve sent_at=now() olarak güncelleme
4. THE System SHALL tek seferde maksimum 100 bildirim işlemeli (performans için)
5. WHEN bildirim gönderimi başarısız olursa, THE System SHALL hatayı loglayıp diğer bildirimlere devam etmeli

### Gereksinim 12: Real-time Bildirim İletimi

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, bildirimleri gerçek zamanlı olarak almak istiyorum, böylece sayfayı yenilememe gerek kalmaz.

#### Kabul Kriterleri

1. THE System SHALL Socket.IO kullanarak real-time bildirim gönderme
2. WHEN kullanıcı sisteme giriş yaptığında, THE System SHALL kullanıcıyı user_{user_id} room'una eklemeli
3. WHEN bildirim gönderildiğinde, THE System SHALL 'new_notification' event'ini emit etmeli
4. THE System SHALL bildirim payload'ında id, task_id, message, type, created_at alanlarını içermeli

### Gereksinim 13: Bildirim Listeleme

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, geçmiş bildirimlerimi görmek istiyorum, böylece kaçırdığım bildirimleri kontrol edebilirim.

#### Kabul Kriterleri

1. THE System SHALL kullanıcının bildirimlerini workspace_id ile filtreleyerek getirmeli
2. THE System SHALL sadece is_sent=TRUE olan bildirimleri listeleme
3. WHEN unread_only=true parametresi gönderildiğinde, THE System SHALL sadece is_read=FALSE bildirimleri döndürmeli
4. THE System SHALL bildirimleri created_at'e göre azalan sırada döndürmeli
5. THE System SHALL maksimum 50 bildirim döndürmeli (limit parametresi ile değiştirilebilir, max 100)

### Gereksinim 14: Bildirim Okundu İşaretleme

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, bildirimleri okundu olarak işaretlemek istiyorum, böylece hangi bildirimleri gördüğümü takip edebilirim.

#### Kabul Kriterleri

1. WHEN kullanıcı bir bildirimi okundu olarak işaretlediğinde, THE System SHALL is_read=TRUE ve read_at=now() olarak güncelleme
2. THE System SHALL sadece bildirimin sahibi olan kullanıcının işaretlemesine izin vermeli
3. WHEN kullanıcı "tümünü okundu işaretle" aksiyonunu çalıştırdığında, THE System SHALL tüm okunmamış bildirimleri güncelleme
4. THE System SHALL güncellenen bildirim sayısını döndürmeli

### Gereksinim 15: Okunmamış Bildirim Sayısı

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, okunmamış bildirim sayımı görmek istiyorum, böylece yeni bildirimlerin farkında olabilirim.

#### Kabul Kriterleri

1. THE System SHALL kullanıcının okunmamış bildirim sayısını hesaplamalı
2. THE System SHALL sadece is_sent=TRUE ve is_read=FALSE bildirimleri saymalı
3. THE System SHALL sayıyı workspace_id ile filtreleyerek hesaplamalı
4. WHEN sayı 0'dan büyükse, THE System SHALL bildirim rozeti göstermeli

### Gereksinim 16: Görev Silme ve Cascade

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, görev sildiğimde ilişkili bildirimlerin de silinmesini istiyorum, böylece veri tutarlılığı sağlanır.

#### Kabul Kriterleri

1. WHEN bir görev silindiğinde, THE System SHALL ilişkili tüm TaskNotification kayıtlarını silmeli (CASCADE)
2. THE System SHALL silme işlemini transaction içinde yapmalı
3. WHEN silme başarısız olursa, THE System SHALL rollback yapmalı

### Gereksinim 17: Workspace İzolasyonu

**Kullanıcı Hikayesi:** Bir sistem yöneticisi olarak, her workspace'in verilerinin izole olmasını istiyorum, böylece veri güvenliği sağlanır.

#### Kabul Kriterleri

1. THE System SHALL her Task kaydında workspace_id foreign key bulundurmalı
2. THE System SHALL her TaskNotification kaydında workspace_id foreign key bulundurmalı
3. THE System SHALL her NotificationPreference kaydında workspace_id foreign key bulundurmalı
4. WHEN veri sorgulanırken, THE System SHALL mutlaka workspace_id filtresi uygulamalı
5. THE System SHALL workspace_id NULL olamaz constraint'i uygulamalı

### Gereksinim 18: Performans Optimizasyonu

**Kullanıcı Hikayesi:** Bir sistem yöneticisi olarak, sistemin Render Free Plan (512MB RAM) üzerinde verimli çalışmasını istiyorum, böylece maliyet düşük kalır.

#### Kabul Kriterleri

1. THE System SHALL Task tablosunda (workspace_id, start_time) composite index bulundurmalı
2. THE System SHALL TaskNotification tablosunda (is_sent, notify_at) composite index bulundurmalı
3. THE System SHALL TaskNotification tablosunda (user_id, is_read) composite index bulundurmalı
4. WHEN takvim sorgusu yapılırken, THE System SHALL eager loading kullanmalı (N+1 query önleme)
5. WHEN background job çalıştırılırken, THE System SHALL batch processing yapmalı (workspace bazında)

### Gereksinim 19: Hata Yönetimi ve Rollback

**Kullanıcı Hikayesi:** Bir geliştirici olarak, veritabanı işlemlerinde hata oluştuğunda rollback yapılmasını istiyorum, böylece veri tutarlılığı korunur.

#### Kabul Kriterleri

1. WHEN db.session.commit() başarısız olursa, THE System SHALL db.session.rollback() çağırmalı
2. THE System SHALL hata mesajını loglayıp kullanıcıya anlamlı hata döndürmeli
3. WHEN background job'da hata oluşursa, THE System SHALL hatayı loglayıp diğer job'ların çalışmasına devam etmeli
4. THE System SHALL tüm kritik işlemleri try/except bloğu içinde yapmalı

### Gereksinim 20: Activity Log Kaydı

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, görev üzerinde yapılan değişikliklerin kaydını görmek istiyorum, böylece geçmişi takip edebilirim.

#### Kabul Kriterleri

1. WHEN görev oluşturulduğunda, THE System SHALL 'task_created' activity log kaydı oluşturmalı
2. WHEN görev güncellendiğinde, THE System SHALL 'task_updated' activity log kaydı oluşturmalı
3. THE System SHALL activity log'da workspace_id, user_id, task_id bilgilerini kaydetmeli
4. THE System SHALL activity log'da değişiklik detaylarını body alanında saklamalı

### Gereksinim 21: Timezone Desteği

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, görevlerimi kendi timezone'umda görmek istiyorum, böylece zaman karmaşası yaşamam.

#### Kabul Kriterleri

1. THE System SHALL her görevde timezone bilgisi saklamalı
2. WHEN timezone belirtilmezse, THE System SHALL varsayılan olarak 'UTC' kullanmalı
3. THE System SHALL pytz kütüphanesi kullanarak timezone dönüşümlerini yapmalı
4. WHEN frontend'de görev oluşturulurken, THE System SHALL kullanıcının browser timezone'unu otomatik algılamalı

### Gereksinim 22: Görev Süresi Hesaplama

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, görevin ne kadar süreceğini görmek istiyorum, böylece zamanımı planlayabilirim.

#### Kabul Kriterleri

1. THE System SHALL görev süresini dakika cinsinden hesaplayan duration_minutes() metodu sağlamalı
2. WHEN start_time veya end_time NULL ise, THE System SHALL NULL döndürmeli
3. THE System SHALL süreyi end_time - start_time olarak hesaplamalı

### Gereksinim 23: Görev Overdue Kontrolü

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, bir görevin süresinin geçip geçmediğini kontrol etmek istiyorum, böylece geciken görevleri görebilirim.

#### Kabul Kriterleri

1. THE System SHALL is_overdue() metodu sağlamalı
2. WHEN görev status'ü completed veya cancelled ise, THE System SHALL FALSE döndürmeli
3. WHEN end_time NULL ise, THE System SHALL FALSE döndürmeli
4. WHEN end_time geçmişte ve status pending ise, THE System SHALL TRUE döndürmeli

### Gereksinim 24: Takvim Event Formatı Dönüşümü

**Kullanıcı Hikayesi:** Bir geliştirici olarak, görevlerin takvim event formatına dönüştürülmesini istiyorum, böylece frontend entegrasyonu kolay olur.

#### Kabul Kriterleri

1. THE System SHALL to_calendar_event() metodu sağlamalı
2. THE System SHALL event formatında id, title, start, end, type, status, color alanlarını içermeli
3. THE System SHALL extendedProps içinde description, priority, contact_id, company_id, deal_id bilgilerini saklamalı
4. THE System SHALL görev tipine göre renk kodu atamalı

### Gereksinim 25: API Endpoint Güvenliği

**Kullanıcı Hikayesi:** Bir güvenlik uzmanı olarak, tüm API endpoint'lerinin kimlik doğrulaması gerektirmesini istiyorum, böylece yetkisiz erişim önlenir.

#### Kabul Kriterleri

1. THE System SHALL tüm takvim ve bildirim endpoint'lerinde @login_required decorator kullanmalı
2. WHEN kullanıcı oturum açmamışsa, THE System SHALL 401 Unauthorized hatası döndürmeli
3. THE System SHALL session'dan workspace_id ve user_id bilgilerini almalı
4. WHEN workspace_id session'da yoksa, THE System SHALL 400 Bad Request hatası döndürmeli

### Gereksinim 26: Input Validasyonu

**Kullanıcı Hikayesi:** Bir geliştirici olarak, kullanıcı girdilerinin validate edilmesini istiyorum, böylece geçersiz veri veritabanına girmez.

#### Kabul Kriterleri

1. WHEN görev başlığı boş ise, THE System SHALL "Görev başlığı zorunludur" hatası döndürmeli
2. WHEN start_time >= end_time ise, THE System SHALL "Bitiş zamanı başlangıç zamanından sonra olmalıdır" hatası döndürmeli
3. THE System SHALL tarih string'lerini datetime'a dönüştürürken hata kontrolü yapmalı
4. WHEN geçersiz tarih formatı gönderilirse, THE System SHALL "Invalid date format" hatası döndürmeli

### Gereksinim 27: Frontend XSS Koruması

**Kullanıcı Hikayesi:** Bir güvenlik uzmanı olarak, frontend'de XSS saldırılarına karşı korunmak istiyorum, böylece kullanıcı verileri güvende olur.

#### Kabul Kriterleri

1. THE System SHALL kullanıcı girdilerini HTML'e yazdırmadan önce escape etmeli
2. THE System SHALL escapeHtml() fonksiyonu kullanmalı
3. THE System SHALL &, <, >, ", ' karakterlerini HTML entity'lere dönüştürmeli

### Gereksinim 28: Background Scheduler Başlatma

**Kullanıcı Hikayesi:** Bir sistem yöneticisi olarak, uygulama başladığında background scheduler'ın otomatik başlamasını istiyorum, böylece manuel müdahale gerekmez.

#### Kabul Kriterleri

1. THE System SHALL app.py'de TaskScheduler.init_scheduler(app) çağırmalı
2. THE System SHALL scheduler'ı daemon=True modunda başlatmalı
3. THE System SHALL uygulama kapanırken atexit.register ile scheduler'ı kapatmalı
4. WHEN scheduler zaten başlatılmışsa, THE System SHALL warning loglayıp tekrar başlatmamalı

### Gereksinim 29: Migration Script Oluşturma

**Kullanıcı Hikayesi:** Bir geliştirici olarak, model değişikliklerinin migration script'leri ile yönetilmesini istiyorum, böylece veritabanı versiyonlaması yapılır.

#### Kabul Kriterleri

1. THE System SHALL Task modeline start_time, end_time, timezone, task_type, contact_id kolonlarını eklemeli
2. THE System SHALL TaskNotification tablosunu oluşturmalı
3. THE System SHALL NotificationPreference tablosunu oluşturmalı
4. THE System SHALL gerekli index'leri oluşturmalı
5. THE System SHALL app.py run_migrations() fonksiyonunu güncelleme (Render Free Tier için)

### Gereksinim 30: Bildirim Sesi

**Kullanıcı Hikayesi:** Bir kullanıcı olarak, yeni bildirim geldiğinde ses duymak istiyorum, böylece bildirimin farkına varırım.

#### Kabul Kriterleri

1. WHEN yeni bildirim geldiğinde, THE System SHALL bildirim sesi çalmalı
2. THE System SHALL ses seviyesini 0.3 (30%) olarak ayarlamalı
3. WHEN ses çalmazsa (tarayıcı izni yok), THE System SHALL sessizce devam etmeli (hata fırlatmamalı)

