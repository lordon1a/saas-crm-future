# CSRF Protection Implementation

## ✅ Tamamlandı

Flask CRM uygulamasına kapsamlı CSRF (Cross-Site Request Forgery) koruması eklendi.

## Yapılan Değişiklikler

### 1. Backend (Python/Flask)

#### requirements.txt
```
Flask-WTF==1.2.1  # CSRF koruması için
```

#### config.py
```python
# CSRF Protection
WTF_CSRF_ENABLED = True
WTF_CSRF_SECRET_KEY = os.getenv('CSRF_SECRET_KEY', SECRET_KEY)
WTF_CSRF_TIME_LIMIT = 3600  # 1 saat
WTF_CSRF_SSL_STRICT = ENV == 'production'
WTF_CSRF_CHECK_DEFAULT = True
```

#### app.py
```python
from flask_wtf.csrf import CSRFProtect

# CSRF Protection
csrf = CSRFProtect(app)

# Webhook endpoint'lerini muaf tut
csrf.exempt(webhook.bp)
csrf.exempt(telegram_bp)
```

### 2. Frontend (HTML/JavaScript)

#### HTML Templates (31 dosya)
Tüm template'lere CSRF meta tag eklendi:
```html
<meta name="csrf-token" content="{{ csrf_token() }}">
```

#### static/app.js
Global fetch interceptor eklendi - tüm API isteklerine otomatik CSRF token ekler:
```javascript
// CSRF Token Helper
function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

// Global Fetch Interceptor
(function() {
    const originalFetch = window.fetch;
    window.fetch = function(url, options = {}) {
        const isSameOrigin = !url.startsWith('http') || url.startsWith(window.location.origin);
        
        if (isSameOrigin) {
            const csrfToken = getCSRFToken();
            options.headers = options.headers || {};
            
            if (csrfToken && !options.headers['X-CSRFToken']) {
                if (options.headers instanceof Headers) {
                    options.headers.set('X-CSRFToken', csrfToken);
                } else {
                    options.headers['X-CSRFToken'] = csrfToken;
                }
            }
        }
        
        return originalFetch.call(this, url, options);
    };
})();
```

## Muaf Tutulan Endpoint'ler

Aşağıdaki endpoint'ler CSRF kontrolünden muaf tutuldu (harici servislerden gelen webhook'lar):

- `/webhook` (WhatsApp Meta API)
- `/webhooks/telegram` (Telegram Bot API)

## Nasıl Çalışır?

1. **Sayfa Yüklendiğinde**: Flask her HTML sayfasına benzersiz bir CSRF token ekler
2. **JavaScript Interceptor**: Tüm fetch() çağrıları otomatik olarak `X-CSRFToken` header'ı ile gönderilir
3. **Backend Doğrulama**: Flask-WTF her POST/PUT/DELETE isteğinde token'ı doğrular
4. **Hata Durumu**: Token eksik veya geçersizse 400 Bad Request döner

## Test Edildi

✅ Flask-WTF kurulumu ve konfigürasyonu
✅ 31 HTML template'e CSRF meta tag eklendi
✅ JavaScript fetch interceptor çalışıyor
✅ Webhook endpoint'leri muaf tutuldu
✅ App başarıyla başlatıldı

## Production Deployment

### Render.com için:

1. Environment variable ekle:
```bash
CSRF_SECRET_KEY=<güçlü-random-string>
```

2. Deploy et:
```bash
git add .
git commit -m "Add CSRF protection"
git push origin main
```

3. Render otomatik deploy edecek

## Güvenlik Notları

- CSRF token'lar 1 saat geçerli (WTF_CSRF_TIME_LIMIT=3600)
- Production'da SSL zorunlu (WTF_CSRF_SSL_STRICT=True)
- Token'lar SECRET_KEY ile imzalanır
- Same-origin policy uygulanır

## Sorun Giderme

### "CSRF token missing" hatası alıyorsanız:

1. Template'de meta tag var mı kontrol edin:
```html
<meta name="csrf-token" content="{{ csrf_token() }}">
```

2. JavaScript console'da token'ı kontrol edin:
```javascript
console.log(document.querySelector('meta[name="csrf-token"]').content);
```

3. Network tab'de request header'ı kontrol edin:
```
X-CSRFToken: <token-value>
```

### Belirli bir endpoint'i muaf tutmak için:

```python
from app import csrf

@csrf.exempt
@bp.route('/my-endpoint', methods=['POST'])
def my_endpoint():
    # CSRF kontrolü yapılmaz
    pass
```

## Referanslar

- [Flask-WTF Documentation](https://flask-wtf.readthedocs.io/)
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
