# Bugfix Requirements Document

## Introduction

CSV içe aktarma işlemi sırasında yinelenen kayıt kontrolü yanlış çalışmaktadır. Sistem, email kontrolü başarısız olduğunda isim kontrolüne geçmekte ve bu durum farklı email adreslerine sahip ancak aynı isme sahip kişilerin yanlışlıkla "duplicate" olarak işaretlenmesine neden olmaktadır. Bu bug, 5000 kayıtlık bir CSV dosyasının boş bir workspace'e içe aktarılması sırasında 2641 kaydın yanlışlıkla atlanmasına yol açmıştır.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN bir kişinin email adresi CSV'de mevcut ancak veritabanında bu email adresi bulunamadığında THEN sistem isim kontrolüne geçer ve aynı isimli başka bir kişi varsa (farklı email'e sahip olsa bile) kaydı "duplicate" olarak işaretler

1.2 WHEN aynı isimde (first_name + last_name) ancak farklı email adreslerine sahip birden fazla kişi CSV'de bulunduğunda THEN sistem ilk kayıttan sonraki tüm kayıtları "duplicate" olarak işaretler ve atlar

1.3 WHEN boş bir veritabanına (hiç kayıt yok) 5000 kayıtlık CSV içe aktarıldığında THEN sistem 2641 kaydı yanlışlıkla "duplicate" olarak raporlar

### Expected Behavior (Correct)

2.1 WHEN bir kişinin email adresi CSV'de mevcut ve veritabanında bu email adresi bulunamadığında THEN sistem isim kontrolü yapmamalı ve kaydı yeni kayıt olarak eklemelidir

2.2 WHEN aynı isimde (first_name + last_name) ancak farklı email adreslerine sahip birden fazla kişi CSV'de bulunduğunda THEN sistem her birini ayrı kayıt olarak eklemelidir (email farklı olduğu için duplicate değildir)

2.3 WHEN email adresi olmayan bir kayıt için duplicate kontrolü yapılırken THEN sistem SADECE isim (first_name + last_name) kombinasyonunu kontrol etmelidir

2.4 WHEN email adresi olan bir kayıt için duplicate kontrolü yapılırken THEN sistem SADECE email adresini kontrol etmelidir (isim kontrolü yapmamalıdır)

### Unchanged Behavior (Regression Prevention)

3.1 WHEN aynı email adresine sahip iki kayıt içe aktarılmaya çalışıldığında THEN sistem ikinci kaydı duplicate olarak işaretlemeye devam etmelidir

3.2 WHEN email adresi olmayan ve aynı isimde (first_name + last_name) iki kayıt içe aktarılmaya çalışıldığında THEN sistem ikinci kaydı duplicate olarak işaretlemeye devam etmelidir

3.3 WHEN duplicate_action parametresi 'skip', 'update', 'create', veya 'create_with_suffix' olarak ayarlandığında THEN sistem bu ayarlara göre davranmaya devam etmelidir

3.4 WHEN workspace_id ile multi-tenant izolasyon kontrolleri yapılırken THEN sistem farklı workspace'lerdeki kayıtları birbirinden izole tutmaya devam etmelidir

3.5 WHEN company_name ile şirket eşleştirmesi yapılırken THEN sistem mevcut şirket bulma/oluşturma mantığını korumaya devam etmelidir
