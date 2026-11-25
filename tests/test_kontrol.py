"""Son teslim kontrolü kararları ve fiş yazımı."""

import json
import subprocess

import pytest

from teslim import fis, kontrol

R = "sahip/repo"
NOREPLY = "1+kisi@users.noreply.github.com"


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    adlar = tmp_path / "adlar.txt"
    adlar.write_text("Zeynepgil\n", encoding="utf-8")
    monkeypatch.setenv("TESLIM_ADLAR", str(adlar))
    monkeypatch.setenv("TESLIM_FIS_DIZIN", str(tmp_path / "fis"))
    monkeypatch.setattr(fis, "ref_ozeti", lambda slug, zaman=60: "ozet")
    return tmp_path / "fis"


def calistir(monkeypatch, kalan, kimlik=True, slug=R):
    monkeypatch.setattr(kontrol, "kontrol_kimlik", lambda *a: kontrol.Kontrol("k", kimlik, ""))
    monkeypatch.setattr(kontrol, "github_kontrolleri", lambda s, a, y: ("a" * 40, kalan))
    return kontrol.main([slug])


def test_hepsi_gecerse_fis_yazar(monkeypatch, ortam):
    assert calistir(monkeypatch, [kontrol.Kontrol("t", True, "")]) == 0
    kayit = json.loads(fis.fis_yolu(R, ortam).read_text(encoding="utf-8"))
    assert kayit["ref_ozeti"] == "ozet" and kayit["repo"] == R
    assert fis.sorun(R, ortam, 3600, lambda s: "ozet") is None


@pytest.mark.parametrize("kimlik,gecti", [(False, True), (True, False)])
def test_biri_kalirsa_fis_yok_eskisi_silinir(monkeypatch, ortam, kimlik, gecti):
    ortam.mkdir()
    (ortam / "sahip__repo.json").write_text("{}", encoding="utf-8")
    assert calistir(monkeypatch, [kontrol.Kontrol("t", gecti, "")], kimlik=kimlik) == 1
    assert not (ortam / "sahip__repo.json").exists()


def test_ad_listesi_yoksa_kontrol_yapilamadi(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("TESLIM_ADLAR", str(tmp_path / "yok.txt"))
    assert kontrol.main([R]) == 2
    assert "geçti sayılmaz" in capsys.readouterr().err


def test_gecersiz_slug(monkeypatch, ortam):
    assert kontrol.main(["yanlis"]) == 2


def test_ref_okunamazsa_kontrol_yapilamadi(monkeypatch, ortam):
    def patla(slug, zaman=60):
        raise OSError

    monkeypatch.setattr(fis, "ref_ozeti", patla)
    assert kontrol.main([R]) == 2


@pytest.mark.parametrize("sonuclar,gecti", [([], False), (["success"], True), (["success", "skipped"], True),
                                            (["skipped"], False), (["success", "failure"], False),
                                            (["success", "bitmedi"], False)])
def test_ci_karari(sonuclar, gecti):
    assert kontrol.kontrol_ci(sonuclar).gecti is gecti


def test_tarama_buyuk_dosyayi_gecirmez():
    assert kontrol.kontrol_tarama([], ["dev.bin"]).gecti is False


@pytest.mark.parametrize("adlar,gecti", [(["README.md", "LICENSE"], True), (["README.md"], False), (["LICENSE"], False),
                                         (["readme.rst", "COPYING"], True)])
def test_urun_dosyalari(adlar, gecti):
    assert kontrol.kontrol_dosyalar(adlar).gecti is gecti


def git(repo, *args, eposta=NOREPLY):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", f"user.email={eposta}", "-c",
                    "commit.gpgsign=false", *args], check=True, capture_output=True)


@pytest.fixture
def yerel(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", NOREPLY], check=True)
    for ad in ("README.md", "LICENSE"):
        (r / ad).write_text("x\n", encoding="utf-8")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "ilk")
    return r


def test_yerel_temiz_repo_gecer_fis_yazmaz(ortam, yerel, capsys):
    assert kontrol.main(["--dizin", str(yerel)]) == 0
    assert "SONUÇ: GEÇTİ" in capsys.readouterr().out
    assert not ortam.exists()


def test_yerel_kisisel_eposta_ve_eksik_lisans_kalir(ortam, yerel, capsys):
    git(yerel, "rm", "-q", "LICENSE")
    git(yerel, "commit", "-q", "-m", "c", eposta="kisi" + "@" + "posta-saglayici.com")
    assert kontrol.main(["--dizin", str(yerel)]) == 1
    cikti = capsys.readouterr().out
    assert "[KALDI] ürün dosyaları" in cikti and "[KALDI] geçmiş taraması" in cikti
    assert "posta-saglayici" not in cikti


def test_yerel_kimlik_noreply_degilse_kalir(ortam, yerel):
    subprocess.run(["git", "-C", str(yerel), "config", "user.email", "a" + "@" + "posta-saglayici.com"], check=True)
    assert kontrol.kontrol_kimlik(yerel).gecti is False
    subprocess.run(["git", "-C", str(yerel), "config", "user.email", NOREPLY], check=True)
    assert kontrol.kontrol_kimlik(yerel).gecti is True
