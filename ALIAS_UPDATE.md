# Alias Dictionary Güncelleme ✅

## Sorun
"Kişi - Ünvan" ve "Kişi - Rol" alanları yakalanmıyordu.

## Çözüm
Alias listelerini genişlettim:

### job_title (Ünvan) - ÖNCESİ:
```python
'unvan', 'title', 'pozisyon', 'position', 'jobtitle', 'meslek',
'isunvani', 'gorev', 'rol', 'duty'
```

### job_title (Ünvan) - SONRASI:
```python
'unvan', 'title', 'pozisyon', 'position', 'jobtitle', 'meslek',
'isunvani', 'isunvan', 'kisiünvan', 'kisiünvani', 'kisiünvanı',
'kisiunvan', 'kisiunvani', 'personelunvan', 'calisanunvan',
'ispozisyonu', 'gorevunvani', 'meslekadi', 'pozisyonu'
```

### role (Rol) - ÖNCESİ:
```python
'rol', 'role', 'gorev', 'duty', 'rolunvan'
```

### role (Rol) - SONRASI:
```python
'rol', 'role', 'gorev', 'duty', 'rolunvan', 'kisirol', 'kisirolü',
'kisirolü', 'kisirolu', 'personelrol', 'calisanrol', 'rolü',
'rolu', 'gorevtanimi', 'sorumluluk', 'sorumluluğu', 'görevi'
```

## Test Sonuçları ✅

Normalizasyon testi:
- "Kişi - Ünvan" → "kisiunvan" ✅ (eşleşecek)
- "Kişi - Rol" → "kisirol" ✅ (eşleşecek)
- "Kişi Ünvanı" → "kisiunvani" ✅ (eşleşecek)
- "Kişi Rolü" → "kisirolu" ✅ (eşleşecek)

## Artık Yakalanan Varyasyonlar

### Ünvan için:
- Kişi - Ünvan ✅
- Kişi Ünvan ✅
- Kişi Ünvanı ✅
- İş Unvanı ✅
- Personel Unvan ✅
- Çalışan Unvan ✅
- Pozisyon ✅
- Meslek ✅

### Rol için:
- Kişi - Rol ✅
- Kişi Rol ✅
- Kişi Rolü ✅
- Personel Rol ✅
- Çalışan Rol ✅
- Görev ✅
- Sorumluluk ✅
