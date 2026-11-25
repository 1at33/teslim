"""Ayar: kişiye özel her şey repo dışındaki kullanıcı dosyalarından okunur.

Arama sırası (her biri çağrı anında okunur):

- ayar dosyası:  TESLIM_AYAR > <ayar kökü>/teslim/ayar.toml
- ad listesi:    TESLIM_ADLAR > ayar.toml `adlar_dosyasi` > <ayar kökü>/teslim/kisisel-adlar.txt
- fiş dizini:    TESLIM_FIS_DIZIN > ayar.toml `fis_dizini` > <ayar kökü>/teslim/fis

<ayar kökü>: POSIX'te $XDG_CONFIG_HOME (yoksa ~/.config), Windows'ta %APPDATA%.
Ayar dosyası yoksa ya da bozuksa varsayılanlar kullanılır; bozuk dosya sessizce yutulmaz, `AyarHatasi` fırlar.
"""

from __future__ import annotations

import fnmatch
import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

UYGULAMA = "teslim"
VARSAYILAN_GECERLILIK_SAAT = 24
VARSAYILAN_SAGLAYICI_ESIK = 5

# Ev dizini kökü ve ardından gelen kullanıcı adı. Yer tutucu adlar izinlidir.
EV_YOLU = re.compile(
    r"(?:\b[A-Za-z]:[\\/]+Users[\\/]+|(?<![\w.])/[A-Za-z]/Users/|(?<![\w.])/home/|(?<![\w.])/Users/)"
    r"([A-Za-z0-9][\w.-]*)",
)
IZINLI_EV = frozenset({
    "runner", "user", "kullanici", "kullanıcı", "ornek", "örnek", "example", "username", "public",
    "shared", "default", "you", "sen", "ad", "x", "me",
})


class AyarHatasi(RuntimeError):
    """Ayar dosyası okunamadı ya da biçimi yanlış."""


@dataclass(frozen=True)
class Ayar:
    """Taramanın kullanıcıya özel parçaları. Hepsi isteğe bağlıdır; boşsa o tür taranmaz."""

    ic_iz: tuple[str, ...] = ()  # metinde geçmemesi gereken düz ifadeler (kasa adı, araç adı, takma ad)
    ic_belge: tuple[str, ...] = ()  # geçmişte bulunmaması gereken yol kalıpları (glob), ör. "KARAR*.md"
    saglayicilar: tuple[str, ...] = ()  # tek dosyada liste gibi duramayacak sağlayıcı/model adları
    saglayici_esik: int = VARSAYILAN_SAGLAYICI_ESIK
    izinli_adresler: tuple[str, ...] = ()  # e-posta taramasında izinli ek adresler (bot adresleri vb.)
    gecerlilik_saat: float = VARSAYILAN_GECERLILIK_SAAT
    adlar_dosyasi: str | None = None
    fis_dizini: str | None = None
    kaynak: str | None = field(default=None, compare=False)

    def ic_iz_deseni(self):
        if not self.ic_iz:
            return None
        return re.compile("|".join(re.escape(s) for s in self.ic_iz), re.IGNORECASE)

    def saglayici_deseni(self):
        if not self.saglayicilar:
            return None
        return re.compile(r"\b(" + "|".join(re.escape(s) for s in self.saglayicilar) + r")\b", re.IGNORECASE)

    def ic_belge_mi(self, yol):
        ad = yol.rsplit("/", 1)[-1]
        return any(fnmatch.fnmatch(yol.casefold(), k.casefold()) or fnmatch.fnmatch(ad.casefold(), k.casefold())
                   for k in self.ic_belge)


def ev_yolu_var(metin):
    """Yer tutucu olmayan bir kullanıcı adıyla ev dizini yolu geçiyor mu."""
    return any(m.group(1).casefold() not in IZINLI_EV for m in EV_YOLU.finditer(metin))


def ayar_koku(env=None, ev=None):
    env = os.environ if env is None else env
    ev = Path.home() if ev is None else Path(ev)
    if sys.platform == "win32":
        kok = Path(env["APPDATA"]) if env.get("APPDATA") else ev / "AppData" / "Roaming"
    else:
        kok = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else ev / ".config"
    return kok / UYGULAMA


def ayar_dosyasi(env=None):
    env = os.environ if env is None else env
    if env.get("TESLIM_AYAR"):
        return Path(env["TESLIM_AYAR"]).expanduser()
    return ayar_koku(env) / "ayar.toml"


def _liste(veri, anahtar):
    deger = veri.get(anahtar, [])
    if not isinstance(deger, list) or not all(isinstance(x, str) and x.strip() for x in deger):
        raise AyarHatasi(f"`{anahtar}` boş olmayan metin listesi olmalı")
    return tuple(x.strip() for x in deger)


def _sayi(veri, anahtar, varsayilan):
    deger = veri.get(anahtar, varsayilan)
    if isinstance(deger, bool) or not isinstance(deger, (int, float)) or deger <= 0:
        raise AyarHatasi(f"`{anahtar}` pozitif sayı olmalı")
    return deger


def _yol(veri, anahtar):
    deger = veri.get(anahtar)
    if deger is not None and (not isinstance(deger, str) or not deger.strip()):
        raise AyarHatasi(f"`{anahtar}` yol olmalı")
    return deger


def yukle(yol=None, env=None):
    """Ayar dosyasını okur. Dosya yoksa varsayılan `Ayar()` döner."""
    yol = Path(yol) if yol else ayar_dosyasi(env)
    try:
        ham = yol.read_bytes()
    except FileNotFoundError:
        return Ayar()
    except OSError as exc:
        raise AyarHatasi(f"ayar dosyası okunamadı: {yol.name}") from exc
    try:
        veri = tomllib.loads(ham.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise AyarHatasi(f"ayar dosyası TOML değil: {yol.name}") from exc
    return Ayar(
        ic_iz=_liste(veri, "ic_iz"),
        ic_belge=_liste(veri, "ic_belge"),
        saglayicilar=_liste(veri, "saglayicilar"),
        saglayici_esik=int(_sayi(veri, "saglayici_esik", VARSAYILAN_SAGLAYICI_ESIK)),
        izinli_adresler=_liste(veri, "izinli_adresler"),
        gecerlilik_saat=float(_sayi(veri, "gecerlilik_saat", VARSAYILAN_GECERLILIK_SAAT)),
        adlar_dosyasi=_yol(veri, "adlar_dosyasi"),
        fis_dizini=_yol(veri, "fis_dizini"),
        kaynak=str(yol),
    )


def adlar_dosyasi(ayar=None, env=None):
    env = os.environ if env is None else env
    if env.get("TESLIM_ADLAR"):
        return Path(env["TESLIM_ADLAR"]).expanduser()
    if ayar is not None and ayar.adlar_dosyasi:
        return Path(ayar.adlar_dosyasi).expanduser()
    return ayar_koku(env) / "kisisel-adlar.txt"


def fis_dizini(ayar=None, env=None):
    env = os.environ if env is None else env
    if env.get("TESLIM_FIS_DIZIN"):
        return Path(env["TESLIM_FIS_DIZIN"]).expanduser()
    if ayar is not None and ayar.fis_dizini:
        return Path(ayar.fis_dizini).expanduser()
    return ayar_koku(env) / "fis"
