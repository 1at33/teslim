"""Ayar dosyası, ortam değişkenleri ve varsayılan yollar."""

import sys
from pathlib import Path

import pytest

from teslim import ayar


def test_dosya_yoksa_varsayilan(tmp_path):
    a = ayar.yukle(tmp_path / "yok.toml")
    assert a == ayar.Ayar()
    assert a.ic_iz_deseni() is None and a.saglayici_deseni() is None and not a.ic_belge_mi("TANIM.md")


def test_ornek_ayar_okunur():
    a = ayar.yukle(Path(__file__).resolve().parents[1] / "ornek" / "ayar.ornek.toml")
    assert a.ic_iz and a.ic_belge and len(a.saglayicilar) >= a.saglayici_esik
    assert a.gecerlilik_saat == 24


@pytest.mark.parametrize("metin", ["ic_iz = 'x'", "ic_iz = ['']", "saglayici_esik = 0", "gecerlilik_saat = true",
                                   "fis_dizini = 3", "ic_iz = [", "\xff"])
def test_bozuk_ayar_hata(tmp_path, metin):
    yol = tmp_path / "a.toml"
    yol.write_bytes(metin.encode("latin-1"))
    with pytest.raises(ayar.AyarHatasi):
        ayar.yukle(yol)


def test_ortam_ayar_yolu(tmp_path, monkeypatch):
    yol = tmp_path / "a.toml"
    yol.write_text('ic_iz = ["ornek-kasa"]\n', encoding="utf-8")
    monkeypatch.setenv("TESLIM_AYAR", str(yol))
    assert ayar.yukle().ic_iz == ("ornek-kasa",)


def test_yol_onceligi(tmp_path):
    a = ayar.Ayar(adlar_dosyasi=str(tmp_path / "ayardan.txt"), fis_dizini=str(tmp_path / "ayardan-fis"))
    ortam = {"TESLIM_ADLAR": str(tmp_path / "ortam.txt"), "TESLIM_FIS_DIZIN": str(tmp_path / "ortam-fis")}
    assert ayar.adlar_dosyasi(a, ortam).name == "ortam.txt"
    assert ayar.fis_dizini(a, ortam).name == "ortam-fis"
    assert ayar.adlar_dosyasi(a, {}).name == "ayardan.txt"
    assert ayar.fis_dizini(a, {}).name == "ayardan-fis"


def test_varsayilan_kok(tmp_path):
    ortam = {"APPDATA": str(tmp_path / "ad"), "XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    kok = ayar.ayar_koku(ortam, tmp_path)
    beklenen = tmp_path / ("ad" if sys.platform == "win32" else "xdg") / "teslim"
    assert kok == beklenen
    assert ayar.adlar_dosyasi(None, ortam) == beklenen / "kisisel-adlar.txt"
    assert ayar.fis_dizini(None, ortam) == beklenen / "fis"


@pytest.mark.parametrize("yol,beklenen", [("TANIM.md", True), ("docs/tanim-v2.md", True), ("docs/karar-3.md", True),
                                          ("docs/tanimlar.txt", False), ("README.md", False)])
def test_ic_belge_glob(yol, beklenen):
    a = ayar.Ayar(ic_belge=("TANIM*.md", "docs/karar-*.md"))
    assert a.ic_belge_mi(yol) is beklenen


@pytest.mark.parametrize("metin,var", [
    ("C:" + "\\Users\\ayse\\x", True), ("/ho" + "me/ayse/x", True), ("/Us" + "ers/ayse/x", True),
    ("/c/Us" + "ers/ayse/x", True), ("C:" + "\\Users\\kullanici\\x", False), ("/ho" + "me/runner/work", False),
    ("/usr/lib/python3", False),
])
def test_ev_yolu(metin, var):
    assert ayar.ev_yolu_var(metin) is var
