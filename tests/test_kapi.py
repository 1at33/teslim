"""Yayın kapısı: public/sürüm komutları fişe bağlı, diğer komutlar serbest."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from teslim import ayar as ayar_mod
from teslim import fis
from teslim import kapi as yk

R = "sahip/repo"
SRC = str(Path(__file__).resolve().parents[1] / "src")


@pytest.fixture
def fisdir(tmp_path, monkeypatch):
    d = tmp_path / "fis"
    d.mkdir()
    monkeypatch.setenv("TESLIM_FIS_DIZIN", str(d))
    monkeypatch.setattr(fis, "ref_ozeti", lambda slug, zaman=60: "ozet")
    return d


def yaz(kok, zaman=None, ozet="ozet", repo=R):
    kayit = {"repo": repo, "ref_ozeti": ozet, "zaman": time.time() if zaman is None else zaman}
    (kok / "sahip__repo.json").write_text(json.dumps(kayit), encoding="utf-8")


def denetle(komut, dizin=None):
    return yk.denetle(komut, dizin, ozet_al=lambda slug: fis.ref_ozeti(slug))


@pytest.mark.parametrize("komut", [
    f"gh repo edit {R} --visibility public --accept-visibility-change-consequences",
    f"gh repo edit {R} --visibility=public",
    f"C:/x/gh.exe repo edit {R} --visibility 'public'",
    f"cd /tmp && gh repo edit {R} --visibility public",
    f"gh release create v1.0 --repo {R}",
    f"gh release create v1.0 -R {R} --notes x",
    f"gh api -X PATCH repos/{R} -F private=false",
    f"gh api -X PATCH repos/{R} -f visibility=public",
    f'git commit -m "not" && gh release create v2 -R {R}',
])
def test_fissiz_yayin_reddedilir_fisle_gecer(fisdir, komut):
    assert denetle(komut)
    yaz(fisdir)
    assert denetle(komut) is None


@pytest.mark.parametrize("komut", ["gh repo create x --public", "gh repo create sahip/x --public --source ."])
def test_public_repo_olusturma_fisle_bile_kapali(fisdir, komut):
    yaz(fisdir)
    assert "private" in denetle(komut)


@pytest.mark.parametrize("komut", [
    f"gh repo edit {R} --visibility private",
    f"gh repo view {R}",
    "gh repo create x --private",
    "git push origin main",
    "git push -u origin ozellik/v2-deneme",
    "git status",
    "git log --tags",
    "pytest tests/ -q",
    "ls -la",
    'git commit -m "gh repo create x --public notu"',
    "git commit -m 'gh release create v1 notu'",
    f'gh pr create --title "x" --body "sonra: gh repo edit {R} --visibility public"',
    "cat <<'EOF' > not.md\ngh repo create x --public\nEOF\n",
])
def test_yayin_olmayan_komut_serbest(fisdir, komut):
    assert denetle(komut) is None


def test_suresi_dolmus_fis(fisdir):
    yaz(fisdir, zaman=time.time() - 24 * 3600 - 5)
    assert "süresi" in denetle(f"gh release create v1 -R {R}")


def test_gelecek_tarihli_fis_gecmez(fisdir):
    yaz(fisdir, zaman=time.time() + 3600)
    assert "süresi" in denetle(f"gh release create v1 -R {R}")


def test_gecerlilik_suresi_ayardan(fisdir, tmp_path, monkeypatch):
    ayar = tmp_path / "ayar.toml"
    ayar.write_text("gecerlilik_saat = 1\n", encoding="utf-8")
    monkeypatch.setenv("TESLIM_AYAR", str(ayar))
    yaz(fisdir, zaman=time.time() - 2 * 3600)
    assert "süresi" in denetle(f"gh release create v1 -R {R}")


def test_bozuk_ayar_yayini_gecirmez(fisdir, tmp_path, monkeypatch):
    ayar = tmp_path / "ayar.toml"
    ayar.write_text("gecerlilik_saat = [", encoding="utf-8")
    monkeypatch.setenv("TESLIM_AYAR", str(ayar))
    yaz(fisdir)
    assert "TOML" in denetle(f"gh release create v1 -R {R}")


def test_repo_fisten_sonra_degismis(fisdir):
    yaz(fisdir, ozet="eski")
    assert "değişmiş" in denetle(f"gh release create v1 -R {R}")


def test_baska_reponun_fisi_sayilmaz(fisdir):
    yaz(fisdir, repo="baska/repo")
    assert "fiş yok" in denetle(f"gh release create v1 -R {R}")


def test_bozuk_fis_yok_sayilir(fisdir):
    (fisdir / "sahip__repo.json").write_text("{", encoding="utf-8")
    assert "fiş yok" in denetle(f"gh release create v1 -R {R}")


def test_repo_durumu_okunamazsa_reddeder(fisdir, monkeypatch):
    yaz(fisdir)

    def patla(slug, zaman=60):
        raise OSError

    monkeypatch.setattr(fis, "ref_ozeti", patla)
    assert "okunamadı" in denetle(f"gh release create v1 -R {R}")


def test_hedef_belirsizse_reddeder(fisdir, tmp_path):
    assert "belirlenemedi" in denetle("gh repo edit --visibility public", str(tmp_path))


def test_cok_uzun_yayin_metni_reddedilir(fisdir):
    yaz(fisdir)
    assert "uzun" in denetle(f"gh release create v1 -R {R} " + "x" * (yk.GIRDI_SINIR + 1))


def test_cozulemeyen_yayin_metni_reddedilir(fisdir, monkeypatch):
    def patla(*a):
        raise ValueError

    monkeypatch.setattr(yk, "eylem_bul", patla)
    assert "çözemedi" in denetle(f"gh release create v1 -R {R}")
    assert denetle("git status") is None


@pytest.fixture
def yerel(tmp_path):
    d = tmp_path / "calisma"
    d.mkdir()
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    subprocess.run(["git", "-C", str(d), "remote", "add", "origin", f"https://github.com/{R}.git"], check=True)
    return d


@pytest.mark.parametrize("komut", ["git push --tags", "git push origin v1.2.0", "git push origin refs/tags/x",
                                   "git push --follow-tags", "git push --mirror"])
def test_tag_push_fise_bagli(fisdir, yerel, komut):
    assert R in denetle(komut, str(yerel))
    yaz(fisdir)
    assert denetle(komut, str(yerel)) is None


def test_git_C_ve_cd_hedefi_cozer(fisdir, yerel):
    assert R in denetle(f"git -C {yerel.as_posix()} push --tags")
    assert R in denetle(f"cd {yerel.as_posix()} && git push --tags")


def test_uzak_url_ile_push(fisdir):
    assert R in denetle(f"git push https://github.com/{R}.git --tags")


# hook arayüzü


def hook_girdisi(komut, arac="Bash", cwd=None):
    return json.dumps({"tool_name": arac, "tool_input": {"command": komut}, "cwd": cwd or os.getcwd()})


def test_kanca_ret_json_bicimi(fisdir):
    cikti = yk.kanca(hook_girdisi(f"gh release create v1 -R {R}"))
    ozel = cikti["hookSpecificOutput"]
    assert ozel["hookEventName"] == "PreToolUse"
    assert ozel["permissionDecision"] == "deny"
    assert ozel["permissionDecisionReason"].startswith("yayın kapısı: ")


@pytest.mark.parametrize("ham", ["", "{", "[]", json.dumps({"tool_name": "Read", "tool_input": {"command": "gh repo create x --public"}}),
                                 json.dumps({"tool_name": "Bash", "tool_input": "x"})])
def test_kanca_ilgisiz_ya_da_bozuk_girdide_sessiz(ham):
    assert yk.kanca(ham) is None


def test_kanca_powershell(fisdir):
    assert yk.kanca(hook_girdisi("gh repo create x --public", arac="PowerShell"))


def kos(girdi, tmp_path):
    ortam = {**os.environ, "PYTHONPATH": SRC, "TESLIM_FIS_DIZIN": str(tmp_path / "fis")}
    ortam.pop("PYTHONUTF8", None)
    return subprocess.run([sys.executable, "-m", "teslim.kapi"], input=girdi.encode("utf-8"), capture_output=True,
                          check=True, env=ortam).stdout.decode("ascii")


def test_hook_sureci_red_ve_serbest(tmp_path):
    cikti = kos(hook_girdisi("gh repo create x --public", cwd=str(tmp_path)), tmp_path)
    assert json.loads(cikti)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert kos(hook_girdisi('git commit -m "gh repo create x --public notu"', cwd=str(tmp_path)), tmp_path) == ""
    assert kos(hook_girdisi("git status", cwd=str(tmp_path)), tmp_path) == ""
    assert kos("bozuk", tmp_path) == ""


def test_elle_deneme_kipi(fisdir, capsys):
    assert yk.cli(["--komut", "gh repo create x --public"]) == 1
    assert "RET" in capsys.readouterr().out
    assert yk.cli(["--komut", "git status"]) == 0


def test_kapi_ve_kontrol_ayni_fis_dizinini_kullanir(tmp_path, monkeypatch):
    monkeypatch.setenv("TESLIM_FIS_DIZIN", str(tmp_path / "f"))
    fis.yaz(R, "ozet", "a" * 40, ayar_mod.fis_dizini())
    assert fis.sorun(R, ayar_mod.fis_dizini(ayar_mod.yukle()), 3600, lambda s: "ozet") is None


def test_ref_ozeti_sirasiz_ayni(monkeypatch):
    class S:
        returncode = 0
        stdout = b""

    def kosucu(cikti):
        def f(*a, **k):
            s = S()
            s.stdout = cikti
            return s
        return f

    monkeypatch.setattr(subprocess, "run", kosucu(b"bbb\trefs/heads/a\naaa\trefs/heads/b\n"))
    bir = fis.ref_ozeti(R)
    monkeypatch.setattr(subprocess, "run", kosucu(b"aaa\trefs/heads/b\nbbb\trefs/heads/a\n"))
    assert fis.ref_ozeti(R) == bir
