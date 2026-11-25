"""Son teslim kontrolü: repo public olmadan ya da sürüm çıkmadan önceki son denetim.

Tüm kontroller geçerse repo için süreli fiş yazar; yayın kapısı (`teslim-kapi`) fiş yoksa, süresi dolduysa
ya da repo fişten sonra değiştiyse public yapmayı ve sürüm çıkarmayı reddeder.

Kullanım: teslim SAHIP/REPO          GitHub'daki repo; geçerse fiş yazar
          teslim --dizin YOL         yeni repoyu göndermeden önce yerel kopya; fiş yazmaz
Çıkış kodu: 0 geçti, 1 kaldı, 2 kontrol yapılamadı (geçti sayılmaz). Bulgunun değeri asla yazılmaz.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass

from teslim import ayar as ayar_mod
from teslim import fis, gecmis

LISANS_ADLARI = re.compile(r"^(?:LICENSE|LICENCE|COPYING)", re.IGNORECASE)
GECEN_SONUCLAR = {"success", "skipped", "neutral"}
NOREPLY = "@users.noreply.github.com"


@dataclass(frozen=True)
class Kontrol:
    ad: str
    gecti: bool
    aciklama: str


def _ciktisi(komut, zaman=120):
    try:
        r = subprocess.run(komut, capture_output=True, check=False, timeout=zaman)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise gecmis.GecmisHatasi(f"{komut[0]} çalışmadı") from exc
    if r.returncode:
        raise gecmis.GecmisHatasi(f"{' '.join(komut[:3])} başarısız")
    return r.stdout.decode("utf-8", "replace")


def kontrol_kimlik(dizin=None):
    """Commit'lerde kullanılacak e-posta GitHub noreply mi. Yerel kipte repodaki etkin ayar, yoksa global."""
    komut = ["git", "-C", str(dizin), "config", "user.email"] if dizin else ["git", "config", "--global", "user.email"]
    try:
        eposta = _ciktisi(komut).strip()
    except gecmis.GecmisHatasi:
        eposta = ""
    tamam = eposta.casefold().endswith(NOREPLY)
    return Kontrol("git kimliği", tamam, "e-posta GitHub noreply" if tamam else "e-posta GitHub noreply değil")


def kontrol_tarama(bulgular, atlanan):
    if bulgular or atlanan:
        sayim = Counter(b.tur for b in bulgular)
        parca = [f"{t} {s}" for t, s in sayim.most_common()]
        if atlanan:
            parca.append(f"taranamayan büyük dosya {len(atlanan)}")
        return Kontrol("geçmiş taraması", False, ", ".join(parca))
    return Kontrol("geçmiş taraması", True, "tüm geçmiş, tag'ler ve dalsız commit'ler temiz")


def kontrol_dosyalar(adlar):
    readme = any(a.casefold().startswith("readme") for a in adlar)
    lisans = any(LISANS_ADLARI.match(a) for a in adlar)
    eksik = [ad for ad, var in (("README", readme), ("LICENSE", lisans)) if not var]
    return Kontrol("ürün dosyaları", not eksik, "README ve LICENSE var" if not eksik else "eksik: " + ", ".join(eksik))


def kontrol_ci(sonuclar):
    if not sonuclar:
        return Kontrol("CI", False, "son commit'te CI koşusu yok")
    kalan = [s for s in sonuclar if s not in GECEN_SONUCLAR]
    if kalan or "success" not in sonuclar:
        return Kontrol("CI", False, f"{len(kalan)}/{len(sonuclar)} iş başarısız ya da bitmedi")
    return Kontrol("CI", True, f"son commit'te {len(sonuclar)} iş yeşil")


def github_kontrolleri(slug, adlar, ayar):
    bulgular, atlanan = gecmis.uzak_tara(f"https://github.com/{slug}.git", adlar, gecmis.github_shalari(slug), ayar)
    sha = _ciktisi(["gh", "api", f"repos/{slug}/commits/HEAD", "--jq", ".sha"]).strip()
    dosyalar = _ciktisi(["gh", "api", f"repos/{slug}/contents", "--jq", ".[].name"]).split()
    ci = _ciktisi(["gh", "api", f"repos/{slug}/commits/{sha}/check-runs?per_page=100", "--jq",
                   '.check_runs[] | (.conclusion // "bitmedi")']).split()
    return sha, [kontrol_tarama(bulgular, atlanan), kontrol_dosyalar(dosyalar), kontrol_ci(ci)]


def yerel_kontroller(dizin, adlar, ayar):
    bulgular, atlanan = gecmis.tara(dizin, adlar, ayar=ayar)
    dosyalar = gecmis.git(dizin, "ls-tree", "--name-only", "HEAD").decode("utf-8", "replace").split()
    return [kontrol_tarama(bulgular, atlanan), kontrol_dosyalar(dosyalar)]


def yazdir(baslik, kontroller):
    print(baslik)
    for k in kontroller:
        print(f"[{'GEÇTİ' if k.gecti else 'KALDI'}] {k.ad}: {k.aciklama}")


def _ayar_uyarilari(ayar):
    eksik = [ad for ad, deger in (("ic_iz", ayar.ic_iz), ("ic_belge", ayar.ic_belge),
                                  ("saglayicilar", ayar.saglayicilar)) if not deger]
    if eksik:
        print(f"not: ayarda boş: {', '.join(eksik)}; bu türlerde yalnız yerleşik kalıplar kullanıldı")


def calistir(a):
    try:
        ayar = ayar_mod.yukle(a.ayar)
    except ayar_mod.AyarHatasi as exc:
        raise gecmis.GecmisHatasi(str(exc)) from exc
    adlar = gecmis.kisisel_adlar(ayar_mod.adlar_dosyasi(ayar))
    if not adlar:
        raise gecmis.GecmisHatasi("ad listesi boş ya da yok; ad taraması yapılamaz (TESLIM_ADLAR)")
    if a.dizin:
        kontroller = [kontrol_kimlik(a.dizin), *yerel_kontroller(a.dizin, adlar, ayar)]
        yazdir(f"teslim (yerel ön kontrol): {a.dizin}", kontroller)
        _ayar_uyarilari(ayar)
        gecti = all(k.gecti for k in kontroller)
        print("SONUÇ: " + ("GEÇTİ (yerel; yayın için GitHub'daki repoda yeniden çalıştır)" if gecti else "KALDI"))
        return 0 if gecti else 1
    if not fis.SLUG.match(a.repo or ""):
        raise gecmis.GecmisHatasi("repo SAHIP/REPO biçiminde olmalı")
    dizin = ayar_mod.fis_dizini(ayar)
    fis.fis_yolu(a.repo, dizin).unlink(missing_ok=True)  # kalan ya da yarım kontrolde eski fiş geçerli kalmasın
    try:
        ozet = fis.ref_ozeti(a.repo)  # taramadan önce alınır: arada gelen push fişi geçersiz bırakır
    except OSError as exc:
        raise gecmis.GecmisHatasi("repo ref'leri okunamadı") from exc
    sha, kalan = github_kontrolleri(a.repo, adlar, ayar)
    kontroller = [kontrol_kimlik(), *kalan]
    yazdir(f"teslim: {a.repo} @{sha[:7]}", kontroller)
    _ayar_uyarilari(ayar)
    if all(k.gecti for k in kontroller):
        fis.yaz(a.repo, ozet, sha, dizin)
        print(f"SONUÇ: GEÇTİ, fiş yazıldı. Repo değişirse ya da {ayar.gecerlilik_saat:g} saat geçerse yeniden çalıştır.")
        return 0
    print("SONUÇ: KALDI, yayınlama.")
    return 1


def ayristir(argv=None):
    p = argparse.ArgumentParser(prog="teslim", description=__doc__.splitlines()[0])
    p.add_argument("repo", nargs="?", help="SAHIP/REPO")
    p.add_argument("--dizin", help="yerel git dizini; fiş yazmaz")
    p.add_argument("--ayar", help="ayar.toml yolu (varsayılan: TESLIM_AYAR ya da kullanıcı ayar dizini)")
    return p.parse_args(argv)


def main(argv=None):
    gecmis._utf8_cikti()
    try:
        return calistir(ayristir(argv))
    except gecmis.GecmisHatasi as hata:
        print(f"SONUÇ: KONTROL YAPILAMADI, geçti sayılmaz: {hata}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
