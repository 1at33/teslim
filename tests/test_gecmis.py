"""Git geçmişi taraması. Adresler ve yollar parçalı yazılır: tarayıcılar bu dosyayı yakalamasın."""

import subprocess

import pytest

from teslim import ayar as ayar_mod
from teslim import gecmis

KISISEL = "kisi" + "@" + "posta-saglayici.com"
NOREPLY = "1+kisi@users.noreply.github.com"
AD = "Zeynepgil"


def g(repo, *args, eposta=NOREPLY, committer=None):
    kim = committer or eposta
    ortam = ["-c", "user.name=t", "-c", f"user.email={kim}", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]
    komut = ["git", "-C", str(repo), *ortam, *args]
    if args[0] == "commit":
        komut.append(f"--author=t <{eposta}>")
    return subprocess.run(komut, check=True, capture_output=True, text=True).stdout.strip()


def commit(repo, ad="a.md", icerik="merhaba\n", mesaj="c", **kw):
    (repo / ad).write_text(icerik, encoding="utf-8")
    g(repo, "add", ad)
    g(repo, "commit", "-q", "-m", mesaj, **kw)
    return g(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    return r


AYAR = ayar_mod.Ayar(ic_iz=("ornek-kasa",), ic_belge=("TASLAK*.md", "PLAN*.md", "ic-not-*.md"),
                     saglayicilar=("alfa", "beta", "gama", "delta", "epsilon", "zeta"))


def turler(repo, adlar=(), aralik=None, ayar=AYAR):
    return {b.tur for b in gecmis.tara(repo, adlar, aralik, ayar)[0]}


def test_temiz_repo_bulgu_vermez(repo):
    commit(repo)
    assert gecmis.tara(repo, [AD]) == ([], [])


@pytest.mark.parametrize("adres", ["noreply@github.com",
                                   "a@example.org", "a@baska.example", "9+x@users.noreply.github.com"])
def test_izinli_adresler(repo, adres):
    commit(repo, eposta=adres, mesaj=f"c\n\nCo-authored-by: x <{adres}>")
    assert turler(repo) == set()


def test_yazar_epostasi(repo):
    commit(repo, eposta=KISISEL, committer=NOREPLY)
    assert turler(repo) == {"yazar e-postası"}


def test_committer_epostasi(repo):
    commit(repo, eposta=NOREPLY, committer=KISISEL)
    assert turler(repo) == {"committer e-postası"}


def test_co_authored_by_satiri(repo):
    commit(repo, mesaj=f"c\n\nCo-authored-by: Kisi <{KISISEL}>")
    assert turler(repo) == {"e-posta"}


def test_tag_tagger_epostasi(repo):
    commit(repo)
    g(repo, "tag", "-a", "v1", "-m", "v1", eposta=KISISEL)
    assert turler(repo) == {"tagger e-postası"}


def test_sonradan_silinen_dosya_yakalanir(repo):
    commit(repo, ad="notlar.md", icerik=f"iletisim: {KISISEL}\n")
    g(repo, "rm", "-q", "notlar.md")
    g(repo, "commit", "-q", "-m", "sil")
    assert (repo / "notlar.md").exists() is False
    assert turler(repo) == {"e-posta"}


def test_tum_daldaki_commit_yakalanir(repo):
    commit(repo)
    g(repo, "checkout", "-q", "-b", "yan")
    commit(repo, ad="y.md", eposta=KISISEL, committer=NOREPLY)
    g(repo, "checkout", "-q", "main")
    assert turler(repo) == {"yazar e-postası"}


def test_ad_dosyada_mesajda_buyuk_kucuk_harf(repo):
    commit(repo, icerik=f"{AD.upper()} yazdi\n", mesaj=f"{AD} karari")
    bulgular = gecmis.tara(repo, [AD])[0]
    assert {b.tur for b in bulgular} == {"ad"}
    assert any(b.yer.startswith("dosya") for b in bulgular)
    assert any("mesajı" in b.yer for b in bulgular)


def test_ad_kelime_icinde_eslesmez(repo):
    commit(repo, icerik=f"x{AD}y\n")
    assert turler(repo, [AD]) == set()


def _gecerli_tc():
    d = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    on = (sum(d[0::2]) * 7 - sum(d[1::2])) % 10
    son = (sum(d) + on) % 10
    return "".join(map(str, [*d, on, son]))


def test_tc_metinde_yakalanir_ikilide_yanlis_alarm_vermez(repo):
    tc = _gecerli_tc()
    commit(repo, ad="m.md", icerik=f"tc {tc}\n")
    assert turler(repo) == {"TC kimlik no"}
    b = repo.parent / "b"
    b.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(b)], check=True)
    (b / "x.bin").write_bytes(b"\0\0 " + tc.encode() + b" \0")
    g(b, "add", "x.bin")
    g(b, "commit", "-q", "-m", "c")
    assert turler(b) == set()


def test_ikili_dosyadaki_eposta_yakalanir(repo):
    (repo / "m.pt").write_bytes(b"\0\0 " + KISISEL.encode() + b" \0")
    g(repo, "add", "m.pt")
    g(repo, "commit", "-q", "-m", "c")
    assert turler(repo) == {"e-posta"}


def test_aralik_eskiyi_saymaz_yeniyi_yakalar(repo):
    eski = commit(repo, eposta=KISISEL, committer=NOREPLY)
    temiz = commit(repo, ad="b.md")
    assert turler(repo, aralik=f"{eski}..{temiz}") == set()
    yeni = commit(repo, ad="c.md", mesaj=f"c\n\nCo-authored-by: K <{KISISEL}>")
    assert turler(repo, aralik=f"{temiz}..{yeni}") == {"e-posta"}


def test_buyuk_dosya_sessizce_gecmez(repo, monkeypatch):
    commit(repo, ad="dev.md", icerik="x" * 100)
    monkeypatch.setattr(gecmis, "BLOB_SINIR", 10)
    assert gecmis.tara(repo, [])[1] == ["dev.md"]


def test_force_push_ile_silinen_commit_taranir(tmp_path, repo):
    uzak = tmp_path / "uzak.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(uzak)], check=True)
    subprocess.run(["git", "-C", str(uzak), "config", "uploadpack.allowAnySHA1InWant", "true"], check=True)
    g(repo, "remote", "add", "origin", str(uzak))
    ilk = commit(repo)
    silinecek = commit(repo, ad="s.md", eposta=KISISEL, committer=NOREPLY)
    g(repo, "push", "-q", "origin", "main")
    g(repo, "reset", "-q", "--hard", ilk)
    commit(repo, ad="t.md")
    g(repo, "push", "-q", "--force", "origin", "main")
    assert gecmis.uzak_tara(str(uzak), [], [])[0] == []
    bulgu = gecmis.uzak_tara(str(uzak), [], [silinecek])[0]
    assert {b.tur for b in bulgu} == {"yazar e-postası"}


def test_cekilemeyen_commit_temiz_sayilmaz(tmp_path, repo):
    uzak = tmp_path / "uzak.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(uzak)], check=True)
    g(repo, "remote", "add", "origin", str(uzak))
    commit(repo)
    g(repo, "push", "-q", "origin", "main")
    with pytest.raises(gecmis.GecmisHatasi):
        gecmis.uzak_tara(str(uzak), [], ["a" * 40])


def test_cikti_degeri_yazmaz(repo, capsys):
    commit(repo, eposta=KISISEL, committer=NOREPLY, icerik=f"{KISISEL} {AD}\n", mesaj=AD)
    adlar = repo.parent / "adlar.lst"
    adlar.write_text(AD + "\n", encoding="utf-8")
    assert gecmis.main(["--repo", str(repo), "--adlar", str(adlar)]) == 1
    cikti = capsys.readouterr()
    assert KISISEL not in cikti.out + cikti.err
    assert AD not in cikti.out + cikti.err


def test_ad_listesi_zorunluysa_yoklugu_hata(repo, tmp_path, monkeypatch):
    commit(repo)
    monkeypatch.setattr(gecmis, "kisisel_adlar", lambda *a: [])
    assert gecmis.main(["--repo", str(repo), "--adlar-zorunlu"]) == 2
    assert gecmis.main(["--repo", str(repo)]) == 0
    assert gecmis.main(["--repo", str(repo), "--adlar", str(tmp_path / "yok.lst")]) == 2


def test_gecersiz_aralik_temiz_sayilmaz(repo):
    commit(repo)
    assert gecmis.main(["--repo", str(repo), "--aralik", "yok..yok2"]) == 2


@pytest.mark.parametrize("icerik,tur", [
    ("anahtar " + "sk-" + "a" * 30 + "\n", "sır kalıbı"),
    ("-----BEGIN " + "RSA PRIVATE KEY-----\n", "sır kalıbı"),
    ("yol C:/Us" + "ers/ayse.k/x\n", "kişisel altyapı izi"),
    ("yol /c/Us" + "ers/ayse.k/x\n", "kişisel altyapı izi"),
    ("yol /ho" + "me/ayse/x\n", "kişisel altyapı izi"),
    ("ornek" + "-KASA notu\n", "kişisel altyapı izi"),
    ("alfa beta gama delta epsilon\n", "sağlayıcı listesi"),
])
def test_ic_iz_ve_sir_silinmis_dosyada_da_yakalanir(repo, icerik, tur):
    commit(repo, ad="n.txt", icerik=icerik)
    g(repo, "rm", "-q", "n.txt")
    g(repo, "commit", "-q", "-m", "sil")
    assert turler(repo) == {tur}


def test_az_saglayici_liste_sayilmaz(repo):
    commit(repo, icerik="alfa ve beta destekli\n")
    assert turler(repo) == set()


@pytest.mark.parametrize("ad,tur", [("TASLAK.md", "iç belge"), ("docs/PLAN-85-90.md", "iç belge"), ("alt/ic-not-1.md", "iç belge"),
                                    (".env", "sır dosyası"), (".env.local", "sır dosyası"), ("a/auth.json", "sır dosyası"),
                                    ("k.pem", "sır dosyası")])
def test_yasak_yol_gecmiste_kalsa_da_yakalanir(repo, ad, tur):
    (repo / ad).parent.mkdir(parents=True, exist_ok=True)
    commit(repo, ad=ad)
    g(repo, "rm", "-q", ad)
    g(repo, "commit", "-q", "-m", "sil")
    assert turler(repo) == {tur}


@pytest.mark.parametrize("ad", [".env.example", "README.md", "docs/tanimlar.txt", "keyboard.py"])
def test_masum_yol_yakalanmaz(repo, ad):
    (repo / ad).parent.mkdir(parents=True, exist_ok=True)
    commit(repo, ad=ad)
    assert turler(repo) == set()


def test_ikili_rastgele_bayt_eposta_sayilmaz(repo):
    (repo / "v.mp4").write_bytes(b"\0\0 X@\xc3.\xd6P a@" b"b.c \xfc@" b"h.Xp \0")
    g(repo, "add", "v.mp4")
    g(repo, "commit", "-q", "-m", "c")
    assert turler(repo) == set()


@pytest.mark.parametrize("icerik", ["yol C:" + "/Users/kullanici/x\n", "yol /ho" + "me/runner/work\n"])
def test_yer_tutucu_ev_yolu_yakalanmaz(repo, icerik):
    commit(repo, icerik=icerik)
    assert turler(repo) == set()


def test_ayar_bossa_kullanici_kaliplari_taranmaz(repo):
    commit(repo, ad="TASLAK.md", icerik="ornek" + "-kasa alfa beta gama delta epsilon\n")
    assert turler(repo, ayar=None) == set()
    assert turler(repo) == {"iç belge", "kişisel altyapı izi", "sağlayıcı listesi"}


def test_esik_ayardan_gelir(repo):
    commit(repo, icerik="alfa ve beta\n")
    az = ayar_mod.Ayar(saglayicilar=("alfa", "beta"), saglayici_esik=2)
    assert turler(repo, ayar=az) == {"sağlayıcı listesi"}


def test_izinli_ek_adres_ayardan_gelir(repo):
    commit(repo, eposta=KISISEL, committer=NOREPLY)
    assert turler(repo, ayar=ayar_mod.Ayar(izinli_adresler=(KISISEL.upper(),))) == set()


def test_ad_listesi_yorum_satirini_atlar(tmp_path):
    dosya = tmp_path / "adlar.txt"
    dosya.write_text("# yorum\nZeynepgil\n\n", encoding="utf-8")
    assert gecmis.kisisel_adlar(dosya) == ["Zeynepgil"]


def test_ad_listesi_ortam_degiskeninden(repo, tmp_path, monkeypatch):
    commit(repo, icerik=f"{AD}\n")
    dosya = tmp_path / "adlar.txt"
    dosya.write_text(AD + "\n", encoding="utf-8")
    monkeypatch.setenv("TESLIM_ADLAR", str(dosya))
    assert gecmis.main(["--repo", str(repo), "--adlar-zorunlu"]) == 1


def test_bozuk_ayar_temiz_sayilmaz(repo, tmp_path):
    commit(repo)
    bozuk = tmp_path / "ayar.toml"
    bozuk.write_text("ic_iz = 3\n", encoding="utf-8")
    assert gecmis.main(["--repo", str(repo), "--ayar", str(bozuk)]) == 2
