# Gereksinimler Dokümanı: WhatsApp CRM MVP (Versiyon 1.0)

## Giriş

WhatsApp CRM MVP, işletmelerin WhatsApp üzerinden gelen müşteri mesajlarını merkezi bir arayüzden yönetmesini sağlayan bir sistemdir. Meta WhatsApp Cloud API kullanarak müşteri mesajlarını alır, temsilcilerin yanıt vermesini sağlar ve konuşma geçmişini saklar. İlk versiyon temel mesajlaşma işlevlerine odaklanır ve hızlı deployment için monolitik bir yapı kullanır.

## Sözlük

- **System**: WhatsApp CRM uygulamasının tamamı (backend, frontend, database)
- **Meta_API**: Meta WhatsApp Cloud API servisi
- **Agent**: Sistemi kullanarak müşterilere yanıt veren temsilci/kullanıcı
- **Customer**: WhatsApp üzerinden işletmeye mesaj gönderen kişi
- **Conversation**: Bir müşteri ile yapılan mesajlaşma oturumu
- **Message**: Tek bir mesaj kaydı (gelen veya giden)
- **Webhook**: Meta'nın sisteme mesaj göndermek için kullandığı HTTP endpoint
- **Quick_Reply**: Hazır yanıt şablonu
- **Bearer_Token**: Meta API'ye erişim için kullanılan kimlik doğrulama token'ı

## Gereksinimler

### Gereksinim 1: Webhook Doğrulama ve Kurulum

**Kullanıcı Hikayesi:** Sistem yöneticisi olarak, Meta WhatsApp API'yi uygulamaya bağlayabilmek için webhook doğrulaması yapabilmek istiyorum.

#### Kabul Kriterleri

1. WHEN Meta GET isteği ile /webhook endpoint'ine verify_token gönderdiğinde, THE System SHALL token'ı doğrulayıp challenge değerini geri döndürmeli
2. IF verify_token yanlış ise, THEN THE System SHALL 403 Forbidden hatası döndürmeli
3. THE System SHALL webhook doğrulamasını sadece bir kez başarıyla tamamlamalı

### Gereksinim 2: Gelen Mesaj Alma ve İşleme

**Kullanıcı Hikayesi:** Müşteri olarak, WhatsApp'tan işletmeye mesaj gönderdiğimde, mesajımın sisteme kaydedilmesini ve temsilcilerin görebilmesini istiyorum.

#### Kabul Kriterleri

1. WHEN Meta POST isteği ile /webhook endpoint'ine mesaj gönderdiğinde, THE System SHALL JSON payload'ı parse etmeli
2. WHEN yeni bir telefon numarasından mesaj geldiğinde, THE System SHALL customers tablosunda yeni kayıt oluşturmalı
3. WHEN mevcut bir müşteriden mesaj geldiğinde, THE System SHALL müşteri kaydını phone_number ile bulmalı
4. WHEN müşterinin açık conversation'ı yoksa, THEN THE System SHALL status='open' ile yeni conversation oluşturmalı
5. THE System SHALL mesaj içeriğini messages tablosuna sender_type='customer' olarak kaydetmeli
6. THE System SHALL Meta'dan gelen message_id'yi meta_message_id alanına kaydetmeli
7. THE System SHALL conversation'ın last_message_at değerini güncellenmeli
8. WHEN mesaj kaydedildiğinde, THE System SHALL frontend'e yeni mesaj bildirimi göndermelidir

### Gereksinim 3: Müşteri Yönetimi

**Kullanıcı Hikayesi:** Sistem olarak, WhatsApp'tan mesaj gönderen her müşterinin bilgilerini saklamak ve takip edebilmek istiyorum.

#### Kabul Kriterleri

1. THE System SHALL her müşteri için benzersiz bir phone_number (WA_ID) saklamalı
2. THE System SHALL Meta'dan gelen profile_name bilgisini müşteri kaydına eklemeli
3. THE System SHALL müşteri oluşturulma zamanını created_at alanında saklamalı
4. THE System SHALL aynı telefon numarasına sahip birden fazla müşteri kaydı oluşturmamalı

### Gereksinim 4: Konuşma Yönetimi

**Kullanıcı Hikayesi:** Temsilci olarak, müşterilerle olan konuşmaları organize edebilmek ve durumlarını takip edebilmek istiyorum.

#### Kabul Kriterleri

1. THE System SHALL her conversation için status değeri saklamalı ('open', 'resolved', 'pending')
2. THE System SHALL conversation'lara etiket (tag) atanabilmesini sağlamalı
3. WHEN yeni mesaj geldiğinde veya gönderildiğinde, THE System SHALL conversation'ın last_message_at değerini güncellenmeli
4. THE System SHALL her conversation'ı bir customer_id ile ilişkilendirmeli
5. THE System SHALL conversation'ları last_message_at değerine göre sıralayabilmeli

### Gereksinim 5: Giden Mesaj Gönderme

**Kullanıcı Hikayesi:** Temsilci olarak, müşterilere WhatsApp üzerinden yanıt gönderebilmek istiyorum.

#### Kabul Kriterleri

1. WHEN temsilci arayüzden mesaj gönderdiğinde, THE System SHALL /api/send_message endpoint'ine POST isteği almalı
2. THE System SHALL Meta messages API'ye Bearer Token ile POST isteği göndermelidir
3. WHEN Meta'dan başarılı yanıt geldiğinde, THE System SHALL mesajı messages tablosuna sender_type='agent' olarak kaydetmeli
4. THE System SHALL gönderen temsilcinin ID'sini sender_id alanına kaydetmeli
5. IF Meta API hatası dönerse, THEN THE System SHALL hata mesajını frontend'e iletmeli ve mesajı veritabanına kaydetmemeli
6. THE System SHALL Meta'dan dönen message_id'yi meta_message_id alanına kaydetmeli

### Gereksinim 6: Mesaj Geçmişi Saklama

**Kullanıcı Hikayesi:** Sistem olarak, tüm mesajlaşma geçmişini saklamak ve gerektiğinde görüntüleyebilmek istiyorum.

#### Kabul Kriterleri

1. THE System SHALL her mesaj için sender_type bilgisi saklamalı ('customer' veya 'agent')
2. THE System SHALL mesaj içeriğini message_body alanında saklamalı
3. THE System SHALL her mesajın oluşturulma zamanını created_at alanında saklamalı
4. THE System SHALL mesajları conversation_id ile ilişkilendirmeli
5. WHEN temsilci mesaj gönderdiğinde, THE System SHALL sender_id alanına temsilci ID'sini kaydetmeli
6. WHEN müşteri mesaj gönderdiğinde, THE System SHALL sender_id alanını NULL bırakmalı

### Gereksinim 7: Kullanıcı Kimlik Doğrulama ve Yetkilendirme

**Kullanıcı Hikayesi:** Sistem yöneticisi olarak, farklı yetkilere sahip kullanıcılar (admin ve agent) oluşturabilmek istiyorum.

#### Kabul Kriterleri

1. THE System SHALL her kullanıcı için benzersiz email adresi saklamalı
2. THE System SHALL kullanıcı şifrelerini hash'lenmiş formatta (password_hash) saklamalı
3. THE System SHALL kullanıcı rollerini 'admin' veya 'agent' olarak tanımlamalı
4. THE System SHALL kullanıcı adı (name) ve email bilgilerini saklamalı
5. THE System SHALL aynı email adresine sahip birden fazla kullanıcı kaydı oluşturmamalı

### Gereksinim 8: Konuşma Listesi API

**Kullanıcı Hikayesi:** Temsilci olarak, arayüzde açık konuşmaların listesini görebilmek istiyorum.

#### Kabul Kriterleri

1. WHEN frontend GET /api/conversations isteği gönderdiğinde, THE System SHALL açık konuşmaların listesini döndürmeli
2. THE System SHALL konuşmaları last_message_at değerine göre azalan sırada döndürmeli
3. THE System SHALL her konuşma için customer bilgilerini (phone_number, profile_name) içermeli
4. THE System SHALL her konuşma için status ve tag bilgilerini içermeli
5. THE System SHALL her konuşma için son mesaj zamanını (last_message_at) içermeli

### Gereksinim 9: Mesaj Geçmişi API

**Kullanıcı Hikayesi:** Temsilci olarak, bir konuşmaya tıkladığımda o müşteriyle olan tüm mesaj geçmişini görebilmek istiyorum.

#### Kabul Kriterleri

1. WHEN frontend GET /api/conversations/<id>/messages isteği gönderdiğinde, THE System SHALL o konuşmaya ait tüm mesajları döndürmeli
2. THE System SHALL mesajları created_at değerine göre artan sırada (eskiden yeniye) döndürmeli
3. THE System SHALL her mesaj için sender_type bilgisini içermeli
4. THE System SHALL her mesaj için message_body içeriğini döndürmeli
5. WHEN sender_type='agent' ise, THE System SHALL gönderen temsilcinin adını (name) içermeli

### Gereksinim 10: Konuşma Etiketleme

**Kullanıcı Hikayesi:** Temsilci olarak, konuşmaları kategorize edebilmek için etiket atayabilmek istiyorum.

#### Kabul Kriterleri

1. WHEN frontend PUT /api/conversations/<id>/tag isteği gönderdiğinde, THE System SHALL conversation'ın tag değerini güncellenmeli
2. THE System SHALL tag değerini string olarak kabul etmeli
3. THE System SHALL geçerli tag değerlerini kabul etmeli ('yeni_siparis', 'kargo_sorunu', 'odeme_bekliyor')
4. IF conversation bulunamazsa, THEN THE System SHALL 404 hatası döndürmeli

### Gereksinim 11: Hazır Yanıt Şablonları

**Kullanıcı Hikayesi:** Temsilci olarak, sık kullanılan yanıtları hızlıca gönderebilmek için hazır şablonlar kullanabilmek istiyorum.

#### Kabul Kriterleri

1. THE System SHALL quick_replies tablosunda hazır yanıt şablonlarını saklamalı
2. THE System SHALL her şablon için başlık (title) ve içerik (body) saklamalı
3. THE System SHALL temsilcilerin şablon listesini çekebilmesi için API endpoint sağlamalı
4. WHEN temsilci şablon seçtiğinde, THE System SHALL şablon içeriğini mesaj olarak gönderebilmeli

### Gereksinim 12: Frontend Arayüz Gereksinimleri

**Kullanıcı Hikayesi:** Temsilci olarak, kullanıcı dostu bir arayüzden mesajları görüntüleyebilmek ve yanıt verebilmek istiyorum.

#### Kabul Kriterleri

1. THE System SHALL sol panelde konuşma listesini görüntülemeli
2. THE System SHALL orta panelde seçili konuşmanın mesaj geçmişini görüntülemeli
3. THE System SHALL mesaj gönderme için input alanı ve gönder butonu sağlamalı
4. THE System SHALL yeni mesajları otomatik olarak görüntüleyebilmek için polling veya socket.io kullanmalı
5. THE System SHALL TailwindCSS ile responsive tasarım sağlamalı
6. THE System SHALL her konuşma için müşteri adını ve son mesaj zamanını göstermeli

### Gereksinim 13: Veritabanı İlişkileri ve Bütünlük

**Kullanıcı Hikayesi:** Sistem olarak, veri bütünlüğünü korumak ve ilişkisel verileri doğru şekilde yönetmek istiyorum.

#### Kabul Kriterleri

1. THE System SHALL conversations tablosunda customer_id için foreign key constraint tanımlamalı
2. THE System SHALL messages tablosunda conversation_id için foreign key constraint tanımlamalı
3. THE System SHALL messages tablosunda sender_id için foreign key constraint tanımlamalı (nullable)
4. THE System SHALL PostgreSQL veritabanı kullanmalı
5. THE System SHALL SQLAlchemy ORM kullanarak veritabanı işlemlerini yönetmeli

### Gereksinim 14: MVP Kapsam Sınırlamaları

**Kullanıcı Hikayesi:** Geliştirici olarak, MVP kapsamında nelerin dahil olmadığını net olarak bilmek istiyorum.

#### Kabul Kriterleri

1. THE System SHALL sadece TEXT mesajları desteklemeli (medya gönderimi v1.1'e ertelendi)
2. THE System SHALL otomatik yanıt veya chatbot özelliği içermemeli
3. THE System SHALL gelişmiş raporlama veya dashboard özellikleri içermemeli
4. THE System SHALL tek işletme (single tenant) yapısında çalışmalı
5. THE System SHALL fotoğraf, PDF veya diğer medya dosyalarını göndermemeli

### Gereksinim 15: Hata Yönetimi ve Loglama

**Kullanıcı Hikayesi:** Geliştirici olarak, sistem hatalarını takip edebilmek ve debug yapabilmek istiyorum.

#### Kabul Kriterleri

1. WHEN Meta API hatası oluştuğunda, THE System SHALL hata detaylarını loglayarak kaydetmeli
2. WHEN webhook'a geçersiz veri geldiğinde, THE System SHALL hatayı loglayıp 400 Bad Request döndürmeli
3. THE System SHALL kritik hataları (database bağlantı hatası, API timeout) loglayarak kaydetmeli
4. THE System SHALL her API isteği için response time bilgisini loglayabilmeli
5. IF veritabanı işlemi başarısız olursa, THEN THE System SHALL transaction rollback yapmalı ve hata mesajı döndürmeli
