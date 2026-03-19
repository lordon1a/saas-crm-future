# Quick Start: Pipeline Features

## 🚀 3 Yeni Özellik Eklendi!

### 1. 🔴 Kırmızı Alarm (Visual Rotting)
Bir kart belirlediğiniz süreden uzun süre aynı kolonda kalırsa otomatik olarak kırmızıya döner.

**Nasıl Kullanılır:**
1. Pipeline sayfasında "Düzenle" butonuna tıklayın
2. Her aşama için "Eskime süresi" toggle'ını açın
3. Gün sayısını girin (örn: 7 gün)
4. "Değişiklikleri Kaydet" butonuna tıklayın
5. Artık kartlar belirlenen süreden sonra otomatik kırmızı olacak!

### 2. 📊 Dinamik Tahmin Tablosu (Weighted Forecast)
Kartları sürükledikçe "Weighted Forecast" rakamı anlık güncellenir.

**Nasıl Çalışır:**
- Her aşamanın olasılık yüzdesi var (örn: %25, %50, %75)
- Formül: Deal Değeri × Olasılık Yüzdesi
- Kartı yeni aşamaya taşıdığınızda tahmin otomatik güncellenir
- Üst panelde 3 metrik görürsünüz:
  - **Weighted Forecast**: Ağırlıklı tahmin
  - **Open Deals**: Açık deal sayısı
  - **Total Value**: Toplam değer

### 3. 🔔 Otomatik Görev Atama (Auto-Tasks)
Bir kart 3 gün boyunca hareket etmezse, sistem otomatik hatırlatma görevi oluşturur.

**Nasıl Kullanılır:**
1. Pipeline sayfasında "Auto-Tasks" butonuna tıklayın
2. Sistem tüm "rotting" (eskiyen) deal'ler için görev oluşturur
3. Görevler deal sahibine atanır
4. Görevler "Tasks" sayfasında görünür
5. Badge üzerinde kaç deal'in eskidiğini görebilirsiniz

---

## ⚡ Hızlı Kurulum

### Adım 1: Migration Çalıştır
```bash
python migrations/add_deal_stage_tracking.py
```

### Adım 2: Aşama Ayarlarını Yapılandır
1. `/pipeline` sayfasına git
2. "Düzenle" butonuna tıkla
3. Her aşama için:
   - Olasılık yüzdesini ayarla (0-100)
   - Eskime süresini aktif et ve gün sayısı gir
4. "Değişiklikleri Kaydet"

### Adım 3: Test Et!
1. Bir deal'i 7+ gün eski bir aşamada bırak
2. Sayfayı yenile - kart kırmızı olmalı
3. "Auto-Tasks" butonuna tıkla
4. Tasks sayfasında yeni görev oluştuğunu gör

---

## 🎨 Görsel Örnekler

### Normal Deal Kartı
```
┌─────────────────────────┐
│ Acme Corp Deal          │
│ 🏢 Acme Corporation     │
│ $50,000    📅 Mar 25    │
└─────────────────────────┘
```

### Rotting Deal Kartı (Kırmızı)
```
┌─────────────────────────┐ ← Kırmızı kenarlık
│ ⚠️ 8 days - Follow up!  │ ← Uyarı badge'i
│ Acme Corp Deal          │
│ 🏢 Acme Corporation     │
│ $50,000    📅 Mar 25    │
└─────────────────────────┘
```

### Forecast Paneli
```
┌──────────────────────────────────────────────┐
│ Weighted Forecast: $125,000                  │
│ Open Deals: 15                               │
│ Total Value: $250,000                        │
└──────────────────────────────────────────────┘
```

---

## 📋 Önerilen Ayarlar

### Satış Pipeline Örneği
| Aşama | Olasılık | Eskime Süresi |
|-------|----------|---------------|
| Lead | 10% | 7 gün |
| Qualified | 25% | 5 gün |
| Proposal | 50% | 3 gün |
| Negotiation | 75% | 2 gün |
| Closed Won | 100% | - |

### Müşteri Destek Pipeline Örneği
| Aşama | Olasılık | Eskime Süresi |
|-------|----------|---------------|
| New Ticket | 20% | 1 gün |
| In Progress | 50% | 2 gün |
| Waiting Customer | 30% | 5 gün |
| Resolved | 100% | - |

---

## 🔧 Sorun Giderme

### Kartlar Kırmızı Olmuyor
- Migration çalıştırıldı mı? → `python migrations/add_deal_stage_tracking.py`
- Aşama ayarlarında "Eskime süresi" aktif mi?
- Sayfayı yenileyin (F5)

### Forecast Güncellenmiyor
- `static/pipeline-enhancements.js` dosyası yüklendi mi?
- Browser console'da hata var mı? (F12)
- Sayfayı hard refresh yapın (Ctrl+F5)

### Auto-Tasks Oluşmuyor
- "Auto-Tasks" butonuna tıkladınız mı?
- Rotting deal var mı? (badge'de sayı görünüyor mu?)
- Tasks sayfasını kontrol edin

---

## 💡 İpuçları

1. **Kısa Süreler Kullanın**: Satış hızını artırmak için kısa eskime süreleri belirleyin
2. **Olasılıkları Gerçekçi Tutun**: Geçmiş verilere göre olasılık yüzdelerini ayarlayın
3. **Düzenli Kontrol**: Her sabah "Auto-Tasks" butonuna tıklayarak günü başlatın
4. **Takım Eğitimi**: Kırmızı kartların acil olduğunu takıma bildirin
5. **Raporlama**: Weighted Forecast'ı haftalık satış toplantılarında kullanın

---

## 📞 Destek

Sorularınız için:
- Dokümantasyon: `PIPELINE_FEATURES_IMPLEMENTATION.md`
- API Referansı: Aynı dosyada "API Reference" bölümü
- Teknik Detaylar: Kod içi yorumlar

**Başarılar! 🎉**
