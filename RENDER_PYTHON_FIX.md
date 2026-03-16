# Render Python Version Fix

## Sorun
Render'da Python 3.10.0 kullanılıyor ve bu versiyonda SSL modülünde recursion bug'ı var.

## Çözüm: Render Dashboard'dan Python Versiyonunu Güncelle

### Adım 1: Render Dashboard'a Git
1. https://dashboard.render.com/ adresine git
2. "whatsapp-crm-saas" servisini seç

### Adım 2: Environment Sekmesine Git
1. Sol menüden "Environment" sekmesine tıkla

### Adım 3: Python Version Environment Variable Ekle
1. "Add Environment Variable" butonuna tıkla
2. Key: `PYTHON_VERSION`
3. Value: `3.11.9`
4. "Save Changes" butonuna tıkla

### Adım 4: Manual Deploy Tetikle
1. Sağ üstteki "Manual Deploy" butonuna tıkla
2. "Deploy latest commit" seçeneğini seç
3. Deploy başlayacak (5-7 dakika sürebilir çünkü Python yeniden yüklenecek)

### Adım 5: Deploy Loglarını İzle
1. "Logs" sekmesine git
2. Şu satırı ara: `Using Python version 3.11.9`
3. Deploy tamamlandığında "Live" yazısını göreceksin

### Adım 6: Test Et
1. https://whatsapp-crm-saas.onrender.com/settings adresine git
2. Google Workspace tab'ına tıkla
3. "Google'a Bağlan" butonuna tıkla
4. Bu sefer çalışacak! ✅

## Alternatif: .python-version Dosyası (Daha Kalıcı)

Eğer yukarıdaki yöntem işe yaramazsa, `.python-version` dosyası oluştur:

```bash
echo "3.11.9" > .python-version
git add .python-version
git commit -m "Set Python version to 3.11.9"
git push origin main
```

## Neden Bu Sorun Oluyor?

Python 3.10.0'da `ssl.py` modülünde bir bug var:
- `SSLContext.options` ve `SSLContext.minimum_version` property'lerinde sonsuz döngü oluşuyor
- Bu bug Python 3.10.1+ ve 3.11+ versiyonlarında düzeltilmiş
- Render varsayılan olarak Python 3.10.0 kullanıyor

## Doğrulama

Deploy tamamlandıktan sonra Render logs'larında şunu göreceksin:
```
Using Python version 3.11.9
```

Eğer hala `Python-3.10.0` görüyorsan, environment variable doğru ayarlanmamış demektir.
