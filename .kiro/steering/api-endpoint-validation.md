---
inclusion: auto
---

# API Endpoint Validation - ZORUNLU KONTROL

## ⚠️ KRİTİK KURAL: Her Yeni Buton/Form/AJAX İşlemi İçin

Yeni bir buton, form, modal veya AJAX çağrısı eklerken **MUTLAKA** şu adımları takip et:

### 1. Backend Endpoint Kontrolü (ZORUNLU)

```bash
# Endpoint'in var olup olmadığını kontrol et
grep -r "@.*route.*endpoint_path" routes/
```

**Kontrol Listesi:**
- [ ] Endpoint backend'de tanımlı mı?
- [ ] HTTP metodu doğru mu? (GET/POST/PATCH/DELETE)
- [ ] Route path doğru mu? (/api/v1/... vs /api/...)
- [ ] @login_required decorator var mı?

### 2. Blueprint Prefix Kontrolü

```python
# app.py'de blueprint nasıl register edilmiş?
app.register_blueprint(contacts_bp)  # Prefix YOK
app.register_blueprint(api_bp, url_prefix='/api')  # Prefix VAR
```

**Yaygın Blueprint'ler:**
- `contacts_bp` → Prefix YOK → `/api/v1/contacts`
- `api_bp` → `/api` prefix → `/api/endpoint`
- `tasks_bp` → Prefix YOK → `/api/v1/tasks`
- `pipeline_bp` → Prefix YOK → `/api/v1/pipeline`

### 3. Frontend API Çağrısı Şablonu

```javascript
// ✅ DOĞRU - Endpoint kontrolü yapılmış
async function myFunction() {
    try {
        // Backend: @contacts_bp.route('/api/v1/contacts/filters', methods=['GET'])
        const response = await fetch('/api/v1/contacts/filters');
        
        if (!response.ok) {
            throw new Error(`API failed: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error:', error);
        showToast('İşlem başarısız', 'error');
    }
}

// ❌ YANLIŞ - Endpoint kontrolü yapılmamış
async function myFunction() {
    const response = await fetch('/api/contacts/filters'); // Yanlış path!
    const data = await response.json();
}
```

### 4. Yeni Endpoint Ekleme Protokolü

Eğer endpoint yoksa:

```python
# routes/contacts.py veya ilgili route dosyası

@contacts_bp.route('/api/v1/endpoint-name', methods=['GET', 'POST'])
@login_required
def endpoint_function():
    """Endpoint açıklaması"""
    try:
        workspace_id = session.get('workspace_id')
        user_id = session.get('user_id')
        
        if not workspace_id or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # İş mantığı
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        logger.error(f"Error in endpoint: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error'}), 500
```

## 📋 Mevcut API Endpoint'leri (Referans)

### Contacts API
```
GET    /api/v1/contacts                          # List contacts
GET    /api/v1/contacts/<id>                     # Get single contact
POST   /api/v1/contacts                          # Create contact
PATCH  /api/v1/contacts/<id>                     # Update contact
DELETE /api/v1/contacts/<id>                     # Delete contact
POST   /api/v1/contacts/<id>/restore             # Restore contact
GET    /api/v1/contacts/export                   # Export contacts
POST   /api/v1/contacts/import                   # Import contacts
POST   /api/v1/contacts/bulk-update              # Bulk update
POST   /api/v1/contacts/bulk-delete              # Bulk delete
POST   /api/v1/contacts/bulk-delete-all          # Delete all
POST   /api/v1/contacts/reorder                  # Reorder contacts
POST   /api/v1/contacts/<id>/toggle-star         # Toggle star
POST   /api/v1/contacts/export-filtered          # Export with filters
```

### Saved Filters API
```
POST   /api/v1/contacts/filters                  # Create saved filter
GET    /api/v1/contacts/filters                  # Get saved filters
DELETE /api/v1/contacts/filters/<id>             # Delete filter
POST   /api/v1/contacts/filters/<id>/share       # Share filter
```

### Companies API
```
GET    /api/v1/companies                         # List companies
GET    /api/v1/companies/<id>                    # Get single company
POST   /api/v1/companies                         # Create company
PATCH  /api/v1/companies/<id>                    # Update company
DELETE /api/v1/companies/<id>                    # Delete company
POST   /api/v1/companies/<id>/restore            # Restore company
GET    /api/v1/companies/export                  # Export companies
POST   /api/v1/companies/bulk-delete-all         # Delete all
POST   /api/v1/companies/reorder                 # Reorder companies
```

### Custom Fields API
```
GET    /api/v1/custom-fields/<entity_type>       # Get custom fields
POST   /api/v1/custom-fields                     # Create custom field
PATCH  /api/v1/custom-fields/<id>                # Update custom field
DELETE /api/v1/custom-fields/<id>                # Delete custom field
GET    /api/v1/custom-fields/<entity_type>/<entity_id>/values  # Get values
POST   /api/v1/custom-fields/<entity_type>/<entity_id>/values  # Set values
```

### User Preferences API
```
GET    /api/v1/user-preferences/contacts-columns        # Get column prefs
POST   /api/v1/user-preferences/contacts-columns        # Save column prefs
GET    /api/v1/user-preferences/contacts-column-widths  # Get widths
POST   /api/v1/user-preferences/contacts-column-widths  # Save widths
```

### Pipeline API
```
GET    /api/v1/pipeline/stages                   # Get stages
POST   /api/v1/pipeline/stages                   # Create stage
PATCH  /api/v1/pipeline/stages/<id>              # Update stage
DELETE /api/v1/pipeline/stages/<id>              # Delete stage
POST   /api/v1/pipeline/stages/reorder           # Reorder stages
```

### Tasks API
```
GET    /api/v1/tasks                             # List tasks
POST   /api/v1/tasks                             # Create task
PATCH  /api/v1/tasks/<id>                        # Update task
DELETE /api/v1/tasks/<id>                        # Delete task
POST   /api/v1/tasks/<id>/complete               # Complete task
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

## ⚡ Hızlı Kontrol Checklist

Yeni bir özellik eklerken:

1. ✅ Backend endpoint var mı? → `grep -r "route.*path" routes/`
2. ✅ Blueprint prefix doğru mu? → `grep "register_blueprint" app.py`
3. ✅ HTTP metodu doğru mu? → Route decorator'da kontrol et
4. ✅ Auth var mı? → `@login_required` decorator'ı var mı?
5. ✅ Error handling var mı? → try/except + rollback
6. ✅ Frontend path doğru mu? → Backend route ile eşleşiyor mu?
7. ✅ Response format tutarlı mı? → `jsonify()` kullanılıyor mu?

## 🚨 Yaygın Hatalar

### Hata 1: Blueprint Prefix Unutmak
```javascript
// ❌ YANLIŞ
fetch('/contacts/filters')  // Blueprint prefix unutulmuş

// ✅ DOĞRU
fetch('/api/v1/contacts/filters')  // Tam path
```

### Hata 2: HTTP Metodu Yanlış
```javascript
// Backend: methods=['POST']
// ❌ YANLIŞ
fetch('/api/v1/contacts', { method: 'GET' })

// ✅ DOĞRU
fetch('/api/v1/contacts', { method: 'POST' })
```

### Hata 3: Endpoint Yokken Çağırmak
```javascript
// ❌ YANLIŞ - Endpoint backend'de yok
fetch('/api/v1/contacts/new-feature')  // 404 hatası!

// ✅ DOĞRU - Önce backend'e ekle, sonra frontend'de kullan
```

## 📝 Yeni Özellik Ekleme Sırası

1. **Backend Route Ekle** (routes/*.py)
2. **Test Et** (Postman/curl ile)
3. **Frontend Çağrısı Ekle** (static/*.js)
4. **UI Bağla** (templates/*.html)
5. **Test Et** (Browser'da)

## 🎯 Özet

**HER YENİ BUTON/FORM/AJAX ÇAĞRISINDA:**
1. Backend endpoint'i kontrol et
2. Blueprint prefix'i kontrol et
3. HTTP metodunu kontrol et
4. Path'i doğru yaz
5. Error handling ekle

**UNUTMA:** Endpoint yoksa önce backend'e ekle, sonra frontend'de kullan!
