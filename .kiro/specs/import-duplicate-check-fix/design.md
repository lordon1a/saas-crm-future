# Import Duplicate Check Fix - Bugfix Design

## Overview

CSV içe aktarma işleminde duplicate kontrolü yanlış çalışmaktadır. Mevcut kod, email kontrolü başarısız olduğunda otomatik olarak isim kontrolüne geçmekte ve bu durum farklı email'lere sahip aynı isimli kişilerin yanlışlıkla duplicate sayılmasına neden olmaktadır. Bu bug, 5000 kayıtlık bir CSV'nin boş workspace'e aktarılması sırasında 2641 kaydın yanlışlıkla atlanmasına yol açmıştır.

Fix yaklaşımı: Email varsa SADECE email ile kontrol yap, email yoksa SADECE isim ile kontrol yap. İki kontrol birbirine karışmamalı.

## Glossary

- **Bug_Condition (C)**: Email adresi olan bir kayıt için duplicate kontrolünde hem email hem de isim kontrolünün yapılması durumu
- **Property (P)**: Email varsa sadece email, email yoksa sadece isim ile duplicate kontrolü yapılması
- **Preservation**: Mevcut duplicate action davranışları (skip, update, create, create_with_suffix) ve workspace izolasyonu
- **execute_import()**: `routes/import_wizard.py` dosyasındaki CSV içe aktarma fonksiyonu (satır 646-850)
- **existing_contact**: Veritabanında bulunan duplicate kayıt
- **duplicate_action**: Kullanıcının seçtiği duplicate işlem stratejisi (skip/update/create/create_with_suffix)

## Bug Details

### Bug Condition

Bug, email adresi olan bir kayıt için duplicate kontrolü yapılırken ortaya çıkar. Mevcut kod önce email ile kontrol yapar, bulamazsa isim ile kontrol yapar. Bu mantık, farklı email'lere sahip aynı isimli kişilerin duplicate sayılmasına neden olur.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type ContactRow (CSV satırı)
  OUTPUT: boolean
  
  RETURN input.email IS NOT NULL
         AND input.email IS NOT EMPTY
         AND NOT existsInDB(input.email)
         AND existsInDB_byName(input.first_name, input.last_name)
END FUNCTION
```

### Examples

- **Örnek 1**: CSV'de "Ahmet Yılmaz" (ahmet@firma1.com) ve "Ahmet Yılmaz" (ahmet@firma2.com) var. İkinci kayıt yanlışlıkla duplicate sayılır ve atlanır.
- **Örnek 2**: Veritabanında "Mehmet Demir" (mehmet@x.com) var. CSV'de "Mehmet Demir" (mehmet@y.com) geldiğinde, email farklı olmasına rağmen isim kontrolü nedeniyle duplicate sayılır.
- **Örnek 3**: 5000 kayıtlık CSV'de aynı isimli ancak farklı email'li 2641 kayıt var. Tümü yanlışlıkla atlanır.
- **Edge case**: Email olmayan kayıtlar için isim kontrolü doğru çalışmalı (bu davranış korunmalı).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Aynı email'e sahip kayıtlar duplicate olarak işaretlenmeye devam etmeli
- Email olmayan kayıtlar için isim bazlı duplicate kontrolü çalışmaya devam etmeli
- duplicate_action parametresi (skip/update/create/create_with_suffix) davranışları değişmemeli
- workspace_id ile multi-tenant izolasyon korunmalı
- company_name ile şirket eşleştirme mantığı değişmemeli

**Scope:**
Email adresi olmayan kayıtların duplicate kontrolü tamamen değişmeden kalmalıdır. Bu şunları içerir:
- Email alanı boş olan CSV satırları
- Email alanı NULL olan CSV satırları
- Sadece isim bilgisi olan kayıtlar

## Hypothesized Root Cause

Mevcut koddaki sorun (satır 763-779):

1. **Yanlış Kontrol Mantığı**: Kod önce email kontrolü yapar, sonra `if not existing_contact` ile isim kontrolüne geçer
   ```python
   if email:
       existing_contact = Contact.query.filter_by(..., email=email, ...).first()
   
   if not existing_contact and first_name:  # ← BUG BURASI
       existing_contact = Contact.query.filter_by(..., first_name=first_name, ...).first()
   ```

2. **Fallback Mantığı Hatası**: Email kontrolü başarısız olduğunda (email DB'de yok) otomatik olarak isim kontrolüne geçiyor

3. **Eksik Koşul**: Email varsa isim kontrolü yapılmamalı, ancak kod bunu kontrol etmiyor

4. **Mantıksal Hata**: `if not existing_contact and first_name` koşulu, "email bulunamadı VE isim var" anlamına geliyor, ancak olması gereken "email YOK VE isim var"

## Correctness Properties

Property 1: Bug Condition - Email-Based Duplicate Check

_For any_ CSV satırı where email adresi mevcut ve boş değil, fixed execute_import() fonksiyonu SHALL SADECE email adresine göre duplicate kontrolü yapmalı ve isim kontrolü yapmamalıdır. Farklı email'e sahip aynı isimli kayıtlar ayrı kayıtlar olarak eklenmelidir.

**Validates: Requirements 2.1, 2.2, 2.4**

Property 2: Preservation - Name-Based Duplicate Check for No-Email Records

_For any_ CSV satırı where email adresi yok veya boş, fixed execute_import() fonksiyonu SHALL orijinal fonksiyonla aynı şekilde SADECE isim (first_name + last_name) kombinasyonuna göre duplicate kontrolü yapmalıdır.

**Validates: Requirements 2.3, 3.2**

## Fix Implementation

### Changes Required

**File**: `routes/import_wizard.py`

**Function**: `execute_import()` (satır 763-779)

**Specific Changes**:

1. **Email Kontrolü Koşulunu Değiştir**: Email varsa SADECE email kontrolü yap ve isim kontrolüne geçme
   ```python
   # Mevcut kod:
   if email:
       existing_contact = Contact.query.filter_by(...).first()
   
   if not existing_contact and first_name:  # ← KALDIRILACAK
       existing_contact = Contact.query.filter_by(...).first()
   ```

2. **Yeni Mantık**: Email varsa sadece email, yoksa sadece isim kontrolü
   ```python
   # Yeni kod:
   if email:
       # Email varsa SADECE email ile kontrol et
       existing_contact = Contact.query.filter_by(
           workspace_id=workspace_id,
           email=email,
           is_deleted=False
       ).first()
   else:
       # Email YOKSA SADECE isim ile kontrol et
       if first_name:
           existing_contact = Contact.query.filter_by(
               workspace_id=workspace_id,
               first_name=first_name,
               last_name=last_name,
               is_deleted=False
           ).first()
   ```

3. **Koşul Yapısını Değiştir**: `if-elif` yapısı kullanarak iki kontrolün birbirine karışmasını engelle

4. **Yorum Ekle**: Kodun amacını açıklayan yorum satırları ekle

5. **Test Edilebilirlik**: Değişiklik minimal olmalı, sadece kontrol mantığı değişmeli

## Testing Strategy

### Validation Approach

Testing stratejisi iki aşamalı: önce unfixed kodda bug'ı göster (counterexample), sonra fixed kodda düzgün çalıştığını ve mevcut davranışların korunduğunu doğrula.

### Exploratory Bug Condition Checking

**Goal**: Fix uygulanmadan ÖNCE bug'ı gösteren counterexample'lar bul. Root cause analizini doğrula veya çürüt.

**Test Plan**: Aynı isimli ancak farklı email'li kayıtlar içeren CSV dosyası hazırla. Boş workspace'e import et. UNFIXED kodda ikinci kaydın yanlışlıkla atlandığını gözlemle.

**Test Cases**:
1. **Same Name Different Email Test**: "Ahmet Yılmaz" (ahmet@x.com) ve "Ahmet Yılmaz" (ahmet@y.com) - ikinci kayıt atlanacak (unfixed kodda)
2. **Multiple Same Names Test**: 10 farklı "Mehmet Demir" kaydı (farklı email'ler) - ilk kayıttan sonraki 9 kayıt atlanacak (unfixed kodda)
3. **No Email Same Name Test**: Email olmayan iki "Ali Veli" kaydı - ikinci kayıt doğru şekilde atlanmalı (bu davranış korunmalı)
4. **Mixed Scenario Test**: Bazı kayıtlarda email var, bazılarında yok - email olanlarda isim kontrolü yapılmamalı

**Expected Counterexamples**:
- Farklı email'li aynı isimli kayıtlar duplicate sayılıyor
- Skipped_count sayısı beklenenin çok üzerinde (örnek: 5000 kayıtta 2641 skip)
- Root cause: `if not existing_contact and first_name` koşulu email kontrolünden sonra çalışıyor

### Fix Checking

**Goal**: Bug condition'ı tetikleyen tüm inputlar için fixed fonksiyonun doğru davrandığını doğrula.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := execute_import_fixed(input)
  ASSERT result.imported_count == expected_count
  ASSERT result.skipped_count == 0  # Farklı email'li kayıtlar atlanmamalı
END FOR
```

### Preservation Checking

**Goal**: Bug condition'ı tetiklemeyen tüm inputlar için fixed fonksiyonun orijinal fonksiyonla aynı davrandığını doğrula.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT execute_import_original(input) = execute_import_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing önerilir çünkü:
- Otomatik olarak çok sayıda test case üretir
- Manuel testlerin kaçırabileceği edge case'leri yakalar
- Email olmayan kayıtlar için davranışın değişmediğini güçlü şekilde garanti eder

**Test Plan**: UNFIXED kodda email olmayan kayıtların davranışını gözlemle, sonra bu davranışı yakalayan property-based testler yaz.

**Test Cases**:
1. **No Email Duplicate Preservation**: Email olmayan aynı isimli kayıtlar duplicate sayılmaya devam etmeli
2. **Same Email Duplicate Preservation**: Aynı email'li kayıtlar duplicate sayılmaya devam etmeli
3. **Duplicate Action Preservation**: skip/update/create/create_with_suffix davranışları değişmemeli
4. **Workspace Isolation Preservation**: Farklı workspace'lerdeki kayıtlar birbirini etkilememeli

### Unit Tests

- Email olan kayıtlar için sadece email kontrolü yapıldığını test et
- Email olmayan kayıtlar için sadece isim kontrolü yapıldığını test et
- Aynı email'li kayıtların duplicate sayıldığını test et
- Email olmayan aynı isimli kayıtların duplicate sayıldığını test et
- Farklı email'li aynı isimli kayıtların duplicate sayılmadığını test et

### Property-Based Tests

- Random CSV satırları üret (bazılarında email var, bazılarında yok)
- Email olan kayıtlar için isim kontrolü yapılmadığını doğrula
- Email olmayan kayıtlar için isim kontrolü yapıldığını doğrula
- Workspace izolasyonunun korunduğunu doğrula
- Duplicate action davranışlarının korunduğunu doğrula

### Integration Tests

- 5000 kayıtlık gerçek CSV dosyası ile test et (aynı isimli farklı email'li kayıtlar içeren)
- Boş workspace'e import et ve tüm kayıtların eklendiğini doğrula
- Email olan ve olmayan kayıtların karışık olduğu senaryoları test et
- duplicate_action parametresinin tüm değerleri ile test et (skip/update/create/create_with_suffix)
