# Bugfix Requirements Document

## Introduction

Contacts ve Companies sayfalarında tut-bırak (drag-and-drop) özelliği frontend'de görsel olarak çalışıyor ancak değişiklikler veritabanına kaydedilmiyor. Kullanıcı bir kişiyi veya şirketi sürükleyip başka bir satırın yerine bıraktığında, sayfa yenilendiğinde (F5) öğeler eski konumlarına geri dönüyor. Bu bug, kullanıcıların manuel olarak belirlediği sıralamayı kaybetmelerine neden oluyor.

Ek olarak, Contacts sayfasının UI'ı Companies sayfasına benzetilecek (UI tutarlılığı için).

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN kullanıcı Contacts sayfasında bir kişiyi sürükleyip başka bir satırın yerine bıraktığında THEN satır görsel olarak hareket eder ancak yeni sıralama veritabanına kaydedilmez

1.2 WHEN kullanıcı Companies sayfasında bir şirketi sürükleyip başka bir satırın yerine bıraktığında THEN satır görsel olarak hareket eder ancak yeni sıralama veritabanına kaydedilmez

1.3 WHEN kullanıcı drag-and-drop ile sıralama değiştirdikten sonra sayfayı yenilediğinde (F5) THEN tüm öğeler eski konumlarına geri döner ve kullanıcının yaptığı değişiklikler kaybolur

1.4 WHEN Contact veya Company modeli veritabanından sorgulandığında THEN sıralama bilgisi (display_order/position) bulunmaz çünkü bu alan modelde tanımlı değildir

1.5 WHEN frontend'de drag-and-drop işlemi tamamlandığında THEN backend'e yeni sıralama bilgisini gönderen bir API çağrısı yapılmaz

### Expected Behavior (Correct)

2.1 WHEN kullanıcı Contacts sayfasında bir kişiyi sürükleyip başka bir satırın yerine bıraktığında THEN yeni sıralama backend API'sine gönderilmeli ve veritabanına kaydedilmeli

2.2 WHEN kullanıcı Companies sayfasında bir şirketi sürükleyip başka bir satırın yerine bıraktığında THEN yeni sıralama backend API'sine gönderilmeli ve veritabanına kaydedilmeli

2.3 WHEN kullanıcı drag-and-drop ile sıralama değiştirdikten sonra sayfayı yenilediğinde (F5) THEN öğeler kullanıcının belirlediği sıralamada görüntülenmeli ve değişiklikler korunmalı

2.4 WHEN Contact veya Company modeli veritabanından sorgulandığında THEN display_order alanına göre sıralanmış sonuçlar dönmeli

2.5 WHEN frontend'de drag-and-drop işlemi tamamlandığında THEN backend'e yeni sıralama bilgisini gönderen bir API çağrısı yapılmalı ve başarı/hata durumu kullanıcıya bildirilmeli

2.6 WHEN yeni bir Contact veya Company oluşturulduğunda THEN otomatik olarak en yüksek display_order değeri + 1 atanmalı

2.7 WHEN Contacts sayfası yüklendiğinde THEN UI Companies sayfasına benzer modern tasarımda görüntülenmeli (tutarlılık için)

### Unchanged Behavior (Regression Prevention)

3.1 WHEN kullanıcı drag-and-drop özelliğini kullanmadığında THEN mevcut listeleme, filtreleme ve arama özellikleri aynen çalışmaya devam etmeli

3.2 WHEN Contact veya Company silindiğinde THEN diğer kayıtların display_order değerleri değişmemeli (boşluklar kabul edilebilir)

3.3 WHEN pagination kullanıldığında THEN sayfa geçişleri ve kayıt sayıları doğru çalışmaya devam etmeli

3.4 WHEN kullanıcı filtreleme veya arama yaptığında THEN sonuçlar display_order'a göre sıralanmalı ancak filtreleme/arama mantığı değişmemeli

3.5 WHEN mevcut API endpoint'leri (GET /api/v1/contacts, GET /api/v1/companies) çağrıldığında THEN geriye dönük uyumluluk korunmalı ve mevcut client'lar çalışmaya devam etmeli

3.6 WHEN bulk delete veya diğer toplu işlemler yapıldığında THEN bu işlemler aynen çalışmaya devam etmeli

3.7 WHEN Contact detail panel veya Company detail modal açıldığında THEN mevcut detay görüntüleme özellikleri aynen çalışmalı
