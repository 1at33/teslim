---
name: teslim
description: >-
  Repoyu public yapmadan, sürüm ya da tag çıkarmadan önceki son kontrolü yapar ve fiş yazar.
  Kullan: "son teslim", "repoyu aç", "public yap", "sürüm çıkar", "yayınla", geçmişi temiz yeni repo kurma.
  Kullanma: private repoda olağan commit, PR ya da ara test; bunlar CI'ın işidir.
allowed-tools: Bash(teslim *) Bash(teslim-gecmis *) Read
---

# Son teslim

Kişisel veri, sır ve iç belge dışarı çıkmadan repoyu durdurur. Çıktısı GEÇTİ/KALDI raporu ve geçtiyse süreli
fiştir; `teslim-kapi` hook'u fişsiz public yapma ve sürüm komutlarını reddeder.

## Adımlar

1. Yeni repo kuruluyorsa yerel ön kontrol: `teslim --dizin YOL`. Kanıt: `SONUÇ:` satırı.
2. Repoyu **private** olarak GitHub'a gönder (noreply kimliğiyle), CI'ın bitmesini bekle. Dışarı çıkan eylem:
   kullanıcının onayıyla.
3. Son kontrol: `teslim SAHIP/REPO`. Kanıt: çıkış kodu 0 ve fiş yazıldı satırı.
4. Taramanın göremediklerini dosyaları okuyarak denetle (README'deki "Elle kontrol" listesi), madde başına sonuç yaz.
5. Raporu kullanıcıya göster; onayıyla public yap. Geri alınamaz; onay her repo için ayrıdır.

## Değişmezler

- KALDI ise yayınlanmaz. Geçirmek için ayar, desen ya da fiş elle değiştirilmez.
- Çıkış 2 (kontrol yapılamadı) geçti sayılmaz.
- Geçmişte bulgu varsa temizlik force-push ile yapılmaz; yeni repo açılır, eskisi private kalır.
- Bulgunun değeri rapora ve başka bir modele gitmez; yalnız tür ve yer.
- Temiz tarama güvenli demek değildir: 4. adım atlanmaz.
