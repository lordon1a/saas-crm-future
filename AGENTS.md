# AI Agent Kural Kitapcigi

Bu dokuman, bu repoda calisan AI coding agent'lar icin zorunlu calisma kurallarini tanimlar.

## 1) Temel Ilke
- Once var olan kodu oku, sonra degisiklik yap.
- Gorev kapsami disina cikma; istenmeyen refactor yapma.
- Mevcut route, API ve davranislari bozma.
- Geriye donuk uyumlulugu koru.

## 2) UI/Frontend Kurallari
- Acikca istenmedikce yeni HTML sayfasi olusturma.
- Mevcut Tailwind tasarim dilini, sidebar/topbar yapisini ve renk dilini koru.
- JS selector'lari (id/class/data-*) ile template ogeleri birebir eslesmeli.
- Gorsel duzeltmelerde yalnizca gerekli siniflari degistir; toplu stil dagitma yapma.

## 3) Backend ve Veri Butunlugu
- Mevcut endpoint'leri silme veya davranisini kirma.
- Yeni endpoint eklerken uygun auth decorator kullan.
- DB write islemlerinde commit adimi try/except ile korunmali:
  - Hata durumunda rollback yap.
  - Hata logu kaydet.
- Iliski/cascade/orphan etkilerini kontrol etmeden model iliskisi degistirme.

## 4) Dosya ve Medya Islemleri
- Dosya adlarini guvenli hale getir (secure filename).
- Path traversal riskini engelle.
- Boyut limiti gibi is kurallari hem backend hem UI tarafinda net gorunsun.

## 5) Hata Yonetimi ve Loglama
- Kullaniciya anlasilir hata mesaji don.
- Sunucu tarafinda detayli ama guvenli log tut (hassas veri yazma).
- Sessizce yutulan exception birakma.

## 6) Test ve Dogrulama
- Degisiklikten sonra ilgili dosyalarda syntax/lint/runtime kontrolu yap.
- Mumkunse ilgili endpoint veya UI akisini hizli smoke test ile dogrula.
- Kritik akislarda regressions kontrolu yapmadan gorevi kapatma.

## 7) Git ve Teslim
- Kucuk, anlamli commit'ler at.
- Commit mesaji degisikligin amacini net anlatmali.
- Push oncesi `git status` ve `git diff` kontrolu yap.
- Kullanici acikca istemedikce destruktif git komutlari kullanma.

## 8) Iletisim Standarti
- Kullanici Turkce istiyorsa Turkce devam et.
- Durum guncellemelerini kisa ve net ver.
- Blokaj varsa erken bildir, alternatif oneri sun.

## 9) Bu Repo Icin Ozel Kirmizi Cizgiler
- Yeni HTML sayfasi acma (ozel istek yoksa).
- Mevcut API route'larini kirma/silme.
- Auth'suz yeni API birakma.
- DB commit'i rollback/log korumasi olmadan birakma.

## 10) Oncelik Sirasi
1. Guvenlik
2. Veri butunlugu
3. Mevcut davranisi koruma
4. Kullanici istegine birebir uyum
5. Kod sadeligi
