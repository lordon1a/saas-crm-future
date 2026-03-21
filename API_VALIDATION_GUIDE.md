# API Endpoint Validation System

## 🎯 Amaç

Her yeni buton, form veya AJAX çağrısı eklendiğinde backend endpoint'lerinin unutulmasını önlemek ve API çağrılarını otomatik olarak validate etmek.

## 📁 Dosyalar

1. `.kiro/steering/api-endpoint-validation.md` - Otomatik yüklenen steering kuralları
2. `static/api-validator.js` - Runtime API validation
3. `API_VALIDATION_GUIDE.md` - Bu dosya

## 🚀 Kullanım

### 1. Steering Kuralları (Otomatik)

`.kiro/steering/api-endpoint-validation.md` dosyası her Kiro oturumunda otomatik yüklenir ve şu kontrolleri yapar:

- ✅ Backend endpoint var mı?
- ✅ Blueprint prefix doğru mu?
- ✅ HTTP metodu doğru mu?
- ✅ Auth decorator var mı?
- ✅ Error handling var mı?

### 2. Runtime Validation (Opsiyonel)

`api-validator.js` kullanarak runtime'da endpoint'leri validate edebilirsiniz:

```javascript
// Normal fetch yerine validatedFetch kullanın
const response = await validatedFetch('/api/v1/contacts', {
    method: 'GET'
});

// Eğer endpoint bilinmiyorsa console'da uyarı verir:
// ⚠️ API Endpoint Warning: GET /api/v1/contacts/unknown is not in known endpoints list!
// 💡 Did you mean one of these? ['GET /api/v1/contacts', 'GET /api/v1/contacts/:id']
```

### 3. Yeni Endpoint Ekleme

Backend'e yeni endpoint ekledikten sonra:

```javascript
// api-validator.js'e ekleyin
apiValidator.addEndpoint('POST', '/api/v1/new-feature');

// Veya doğrudan knownEndpoints'e ekleyin
```

## 📋 Checklist: Yeni Özellik Eklerken

```markdown
- [ ] Backend endpoint tanımlı mı?
      → grep -r "@.*route.*path" routes/
      
- [ ] Blueprint prefix doğru mu?
      → grep "register_blueprint" app.py
      
- [ ] HTTP metodu doğru mu?
      → Route decorator'da kontrol et
      
- [ ] @login_required var mı?
      → Route fonksiyonunda kontrol et
      
- [ ] Error handling var mı?
      → try/except + db.session.rollback()
      
- [ ] Frontend path doğru mu?
      → Backend route ile eşleşiyor mu?
      
- [ ] validatedFetch kullanıldı mı?
      → Console'da uyarı var mı?
```

## 🔍 Endpoint Bulma Komutları

```bash
# Tüm route'ları listele
grep -r "@.*\.route" routes/ | grep -v ".pyc"

# Belirli bir endpoint'i ara
grep -r "'/api/v1/contacts'" routes/

# Blueprint'leri listele
grep -r "Blueprint(" routes/

# app.py'de blueprint register'larını gör
grep "register_blueprint" app.py
```

## 🎨 Örnek: Yeni Buton Ekleme

### ❌ YANLIŞ Yaklaşım

```javascript
// 1. Önce frontend'e buton ekle
<button onclick="myNewFeature()">Yeni Özellik</button>

// 2. Sonra fetch çağrısı yap
async function myNewFeature() {
    const res = await fetch('/api/v1/contacts/new-feature'); // 404!
    // ...
}

// 3. Backend'i unutmuşsun!
```

### ✅ DOĞRU Yaklaşım

```python
# 1. Önce backend'e endpoint ekle
# routes/contacts.py

@contacts_bp.route('/api/v1/contacts/new-feature', methods=['POST'])
@login_required
def new_feature():
    """Yeni özellik endpoint'i"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # İş mantığı
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error'}), 500
```

```javascript
// 2. api-validator.js'e ekle
apiValidator.addEndpoint('POST', '/api/v1/contacts/new-feature');

// 3. Frontend'de kullan
async function myNewFeature() {
    try {
        const res = await validatedFetch('/api/v1/contacts/new-feature', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data: 'value' })
        });
        
        if (!res.ok) {
            throw new Error(`API failed: ${res.status}`);
        }
        
        const data = await res.json();
        showToast('Başarılı!', 'success');
        
    } catch (error) {
        console.error('Error:', error);
        showToast('Hata oluştu', 'error');
    }
}

// 4. HTML'e buton ekle
<button onclick="myNewFeature()">Yeni Özellik</button>
```

## 🚨 Yaygın Hatalar ve Çözümleri

### Hata 1: Blueprint Prefix Unutmak

```javascript
// ❌ YANLIŞ
fetch('/contacts/filters')

// ✅ DOĞRU
fetch('/api/v1/contacts/filters')
```

**Çözüm:** `grep "register_blueprint" app.py` ile prefix'i kontrol et

### Hata 2: HTTP Metodu Yanlış

```javascript
// Backend: methods=['POST']
// ❌ YANLIŞ
fetch('/api/v1/contacts', { method: 'GET' })

// ✅ DOĞRU
fetch('/api/v1/contacts', { method: 'POST' })
```

**Çözüm:** Backend route decorator'ında `methods=` parametresini kontrol et

### Hata 3: Endpoint Yokken Çağırmak

```javascript
// ❌ YANLIŞ
fetch('/api/v1/contacts/non-existent') // 404!

// ✅ DOĞRU
// 1. Önce backend'e ekle
// 2. Sonra frontend'de kullan
```

**Çözüm:** `grep -r "route.*path" routes/` ile endpoint'in varlığını kontrol et

## 📊 Mevcut Endpoint'ler

Tüm mevcut endpoint'lerin listesi için:
- `.kiro/steering/api-endpoint-validation.md` dosyasına bakın
- `static/api-validator.js` içindeki `knownEndpoints` objesine bakın

## 🔧 Bakım

### Yeni Endpoint Eklendiğinde

1. Backend'e ekle (routes/*.py)
2. `api-validator.js`'e ekle (knownEndpoints)
3. `.kiro/steering/api-endpoint-validation.md`'yi güncelle

### Endpoint Kaldırıldığında

1. Backend'den kaldır
2. `api-validator.js`'den kaldır
3. Frontend'deki tüm çağrıları kaldır

## 💡 İpuçları

1. **Her zaman validatedFetch kullanın** - Normal fetch yerine
2. **Console'u kontrol edin** - Uyarıları kaçırmayın
3. **Steering dosyasını okuyun** - Her oturumda hatırlatma alırsınız
4. **Endpoint listesini güncel tutun** - Yeni endpoint eklerken unutmayın

## 🎯 Özet

**UNUTMA:**
1. ✅ Önce backend endpoint'i ekle
2. ✅ Sonra api-validator.js'e ekle
3. ✅ En son frontend'de kullan
4. ✅ validatedFetch ile validate et
5. ✅ Console'da uyarı varsa düzelt

---

**Son Güncelleme:** 2026-03-20
**Durum:** ✅ Aktif ve Çalışıyor
