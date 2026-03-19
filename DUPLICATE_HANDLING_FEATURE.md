# Yinelenen Kişiler İçin İçe Aktarma Özelliği

## Genel Bakış

İçe aktarma sihirbazına yinelenen kayıtları tespit etme ve yönetme özelliği eklendi. Kullanıcılar artık içe aktarma sırasında veritabanında zaten mevcut olan kayıtlar için ne yapılacağını seçebilirler.

## Özellikler

### 1. Yinelenen Kayıt Tespiti

Sistem, içe aktarma öncesinde aşağıdaki kriterlere göre yinelenen kayıtları tespit eder:

#### Kişiler için:
- **E-posta eşleşmesi**: Aynı e-posta adresine sahip kayıtlar
- **İsim eşleşmesi**: Aynı ad ve soyada sahip kayıtlar (e-posta yoksa)

#### Şirketler için:
- **Şirket adı eşleşmesi**: Aynı şirket adına sahip kayıtlar

### 2. Yinelenen Kayıt Yönetimi Seçenekleri

Kullanıcılar 3 farklı seçenek arasından birini seçebilir:

#### a) Yinelenen Kayıtları Atla (Varsayılan)
- Mevcut kayıtlar korunur
- Sadece yeni kayıtlar eklenir
- Yinelenen kayıtlar sayılır ve raporlanır

#### b) Mevcut Kayıtları Güncelle
- Yinelenen kayıtların bilgileri yeni verilerle güncellenir
- Tüm alanlar (ad, e-posta, telefon, şirket, vb.) güncellenir
- Özel alanlar da güncellenir veya eklenir

#### c) Yinelenen Kayıt Oluştur
- Aynı bilgilere sahip yeni kayıtlar oluşturulur
- **Önerilmez** - Veritabanında gerçek yinelemeler oluşturur

### 3. Kullanıcı Arayüzü

#### Önizleme Adımında (Step 4):

1. **Yinelenen Kayıt Kartı**
   - Sarı arka plan ile dikkat çekici tasarım
   - Tespit edilen yinelenen kayıt sayısı
   - 3 seçenek için radio button'lar
   - Her seçeneğin açıklaması

2. **Yinelenen Kayıt Detayları**
   - "Yinelenen kayıtları göster" butonu ile açılır/kapanır
   - Her yinelenen kayıt için:
     - Satır numarası
     - Yeni veri (ad, e-posta, telefon, şirket)
     - Eşleşme tipi (e-posta veya isim)
     - Mevcut kayıt bilgileri

3. **Doğrulama Durumu**
   - Yinelenen kayıt varsa mavi renk
   - Hata varsa kırmızı renk
   - Her şey tamam ise yeşil renk

#### Tamamlama Adımında (Step 5):

Sonuç istatistikleri:
- Yeni eklenen kayıtlar
- Güncellenen kayıtlar
- Atlanan kayıtlar
- Başarısız kayıtlar

## Teknik Detaylar

### Backend (routes/import_wizard.py)

#### 1. Validate Endpoint Güncellemeleri
```python
@import_bp.route('/api/v1/import/validate', methods=['POST'])
def validate_import():
    # Yinelenen kayıtları tespit et
    duplicates = []
    
    # E-posta ile kontrol
    if email:
        existing = Contact.query.filter_by(
            workspace_id=workspace_id,
            email=email
        ).first()
    
    # İsim ile kontrol
    if not existing and first_name:
        existing = Contact.query.filter_by(
            workspace_id=workspace_id,
            first_name=first_name,
            last_name=last_name
        ).first()
    
    return jsonify({
        'duplicates': duplicates,
        'duplicate_count': len(duplicates)
    })
```

#### 2. Execute Endpoint Güncellemeleri
```python
@import_bp.route('/api/v1/import/execute', methods=['POST'])
def execute_import():
    duplicate_action = data.get('duplicate_action', 'skip')
    
    if existing_contact:
        if duplicate_action == 'skip':
            skipped_count += 1
            continue
        elif duplicate_action == 'update':
            # Mevcut kaydı güncelle
            existing_contact.first_name = first_name
            # ... diğer alanlar
            updated_count += 1
            continue
    
    return jsonify({
        'imported_rows': imported_count,
        'updated_rows': updated_count,
        'skipped_rows': skipped_count
    })
```

### Frontend (templates/import.html)

#### 1. State Yönetimi
```javascript
const STATE = {
    duplicates: [],  // Yeni eklendi
    // ... diğer state değişkenleri
};
```

#### 2. Yinelenen Kayıt Kartı HTML
- Sarı arka planlı uyarı kartı
- 3 radio button seçeneği
- Detay listesi (açılır/kapanır)

#### 3. JavaScript Fonksiyonları
- `loadPreview()`: Yinelenen kayıtları göster
- `toggleDuplicateDetails()`: Detayları aç/kapa
- `executeImport()`: Seçilen aksiyonu gönder

## Kullanım Senaryoları

### Senaryo 1: Müşteri Listesi Güncelleme
Kullanıcı mevcut müşteri listesini güncellenmiş bilgilerle içe aktarıyor:
1. Dosyayı yükle
2. Alanları eşleştir
3. Önizlemede 50 yinelenen kayıt tespit edildi
4. "Mevcut kayıtları güncelle" seçeneğini seç
5. İçe aktar
6. Sonuç: 50 kayıt güncellendi, 20 yeni kayıt eklendi

### Senaryo 2: Yeni Müşteri Listesi Ekleme
Kullanıcı yeni bir müşteri listesi ekliyor, bazıları zaten sistemde:
1. Dosyayı yükle
2. Alanları eşleştir
3. Önizlemede 10 yinelenen kayıt tespit edildi
4. "Yinelenen kayıtları atla" seçeneğini seç (varsayılan)
5. İçe aktar
6. Sonuç: 10 kayıt atlandı, 90 yeni kayıt eklendi

### Senaryo 3: Farklı Kaynaklardan Veri Birleştirme
Kullanıcı farklı kaynaklardan gelen verileri birleştiriyor:
1. Dosyayı yükle
2. Alanları eşleştir
3. Önizlemede yinelenen kayıt yok
4. İçe aktar
5. Sonuç: 100 yeni kayıt eklendi

## Test Senaryoları

### Test 1: E-posta ile Yineleme Tespiti
- Aynı e-posta adresine sahip 2 kayıt
- Beklenen: 1 yineleme tespit edilmeli

### Test 2: İsim ile Yineleme Tespiti
- Aynı ad ve soyada sahip 2 kayıt (e-posta yok)
- Beklenen: 1 yineleme tespit edilmeli

### Test 3: Atla Aksiyonu
- 5 yinelenen kayıt, "Atla" seçili
- Beklenen: 5 kayıt atlanmalı, skipped_count = 5

### Test 4: Güncelle Aksiyonu
- 5 yinelenen kayıt, "Güncelle" seçili
- Beklenen: 5 kayıt güncellenmeli, updated_count = 5

### Test 5: Özel Alanlar Güncelleme
- Yinelenen kayıt, özel alanlar var, "Güncelle" seçili
- Beklenen: Özel alanlar da güncellenmeli

## Gelecek İyileştirmeler

1. **Akıllı Eşleştirme**: Fuzzy matching ile benzer isimleri tespit et
2. **Toplu Seçim**: Her yinelenen kayıt için ayrı ayrı aksiyon seçme
3. **Önizleme Karşılaştırma**: Eski ve yeni verileri yan yana göster
4. **Yineleme Raporu**: Detaylı yineleme raporu oluştur ve indir
5. **Otomatik Birleştirme**: Akıllı birleştirme algoritması ile en iyi veriyi seç

## Notlar

- Yineleme tespiti workspace bazlıdır
- E-posta eşleşmesi, isim eşleşmesinden önceliklidir
- Özel alanlar da güncelleme işlemine dahildir
- Şirketler için sadece isim eşleşmesi kontrol edilir
