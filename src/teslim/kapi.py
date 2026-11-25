"""Yayın kapısı: geçerli son teslim fişi olmadan repo public yapılamaz, sürüm çıkarılamaz.

Claude Code `PreToolUse` hook'u olarak çalışır: stdin'den hook JSON'unu (tool_name, tool_input, cwd) okur,
kabuk komutunda yayın eylemi bulursa ve fiş geçerli değilse `permissionDecision: deny` basar. Yayın eylemi
olmayan komutlara dokunmaz (çıktı yok, çıkış 0).

Fişe bağlı eylemler: `gh repo edit --visibility public`, `gh release create`, `gh api ... private=false` ya da
`visibility=public`, tag gönderen `git push` (`--tags`, `--follow-tags`, `--mirror`, `refs/tags/`, `v1.2` gibi).
`gh repo create --public` her zaman kapalıdır: repo önce private kurulur, kontrol geçince açılır.

Kuşkuda reddeder: yayın komutu gibi görünen ama çözülemeyen metin geçmez. Commit mesajı, PR gövdesi ve heredoc
içindeki metin komut sayılmaz.

Kullanım: teslim-kapi            hook kipi (stdin JSON)
          teslim-kapi --komut "gh release create v1 -R sahip/repo" [--dizin YOL]   elle deneme
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

from teslim import ayar as ayar_mod
from teslim import fis

KOMUT = "teslim"
ARACLAR = {"Bash", "PowerShell"}
GIRDI_SINIR = 20_000  # bundan uzun yayın benzeri metin çözülmeden reddedilir
IPUCU = re.compile(r"--visibility|--public|release\s+create|--tags|--follow-tags|--mirror|refs/tags/"
                   r"|private=false|visibility=public|\bpush\s[^\n]{0,200}\bv\d")

GH = r"(?:^|[\s(/\\])gh(?:\.exe)?\s+"
GIT_PUSH = re.compile(r"(?:^|[\s(/\\])git(?:\.exe)?\s+((?:-\S+(?:\s+\S+)?\s+){0,8}?)push\b(.*)$", re.DOTALL)
GORUNURLUK = re.compile(GH + r"repo\s+edit\b.*--visibility[=\s]+public\b", re.DOTALL)
YENI_PUBLIC = re.compile(GH + r"repo\s+create\b.*--public\b", re.DOTALL)
SURUM = re.compile(GH + r"release\s+create\b", re.DOTALL)
API_ACMA = re.compile(GH + r"api\b.*\b(?:private=false|visibility=public)\b", re.DOTALL)
TAG_PUSH = re.compile(r"(?:--tags\b|--follow-tags\b|--mirror\b|refs/tags/|(?:^|\s)v\d+(?:\.\d+)*\S*(?:\s|$))")
GITHUB_URL = re.compile(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$")
AYRAC = re.compile(r"[\n;|&]+")
CD = re.compile(r"^\s*(?:cd|pushd|set-location|sl)\s+(\S+)\s*$", re.IGNORECASE)

# Serbest metin taşıyan seçenekler: değerleri komut değildir.
MESAJ_SECENEGI = re.compile(
    r"""(\s(?:-m|--message|--body|--notes|--title|-b|-t|-n))(?:=|\s*)("(?:[^"\\]|\\.)*"|'[^']*')""",
    re.DOTALL,
)
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?:\n|$)", re.DOTALL)


def komut_metni(metin):
    """Mesaj seçeneklerinin değerlerini ve heredoc gövdelerini atar; geriye çalışacak komut kalır."""
    metin = HEREDOC.sub("\n", metin)
    return MESAJ_SECENEGI.sub(r'\1 ""', metin)


def _deger(metin, *secenekler):
    for s in secenekler:
        m = re.search(rf"(?:^|\s){re.escape(s)}[=\s]+(\S+)", metin)
        if m:
            return m[1]
    return None


def _uzak_slug(dizin, uzak="origin"):
    if GITHUB_URL.search(uzak):
        return GITHUB_URL.search(uzak)[1]
    if not dizin or not os.path.isdir(dizin):
        return None
    try:
        r = subprocess.run(["git", "-C", dizin, "remote", "get-url", uzak], capture_output=True, text=True,
                           check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = GITHUB_URL.search(r.stdout.strip()) if r.returncode == 0 else None
    return m[1] if m else None


def _edit_slug(parca, dizin):
    kuyruk = re.split(r"\brepo\s+edit\b", parca, maxsplit=1)[1].split()
    if kuyruk and fis.SLUG.match(kuyruk[0]):
        return kuyruk[0]
    return _uzak_slug(dizin)


def _push_slug(oncesi, sonrasi, dizin):
    c = _deger(oncesi, "-C")
    if c:
        dizin = c if os.path.isabs(c) else os.path.join(dizin or "", c)
    uzak = next((k for k in sonrasi.split() if not k.startswith("-")), "origin")
    return _uzak_slug(dizin, uzak)


def eylem_bul(metin, dizin):
    """Yayın eylemi varsa (ad, slug ya da None) döner; yoksa None."""
    for ham in AYRAC.split(komut_metni(metin)):
        parca = ham.replace('"', "").replace("'", "")
        cd = CD.match(parca)
        if cd:
            hedef = os.path.expanduser(cd[1])
            dizin = hedef if os.path.isabs(hedef) else os.path.join(dizin or "", hedef)
            continue
        if YENI_PUBLIC.search(parca):
            return "public repo oluşturma", None
        if GORUNURLUK.search(parca):
            return "repoyu public yapma", _edit_slug(parca, dizin)
        if SURUM.search(parca):
            return "sürüm çıkarma", _deger(parca, "-R", "--repo") or _uzak_slug(dizin)
        if API_ACMA.search(parca):
            m = re.search(r"repos/([\w.-]+/[\w.-]+)", parca)
            return "repoyu public yapma", m[1] if m else None
        push = GIT_PUSH.search(parca)
        if push and TAG_PUSH.search(push[2]):
            return "tag gönderme", _push_slug(push[1], push[2], dizin)
    return None


def denetle(metin, dizin, ayar=None, ozet_al=None):
    """Reddetme sebebi ya da None."""
    if not IPUCU.search(metin):
        return None  # olağan komut: ayrıştırma yok
    if len(metin) > GIRDI_SINIR:
        return "yayın komutu içeren metin çözümlenemeyecek kadar uzun"
    try:
        bulunan = eylem_bul(metin, dizin)
    except Exception:  # noqa: BLE001  # hook çökmemeli; ipucu taşıyan metin kuşkuda reddedilir
        return "yayın kapısı komutu çözemedi"
    if not bulunan:
        return None
    ad, slug = bulunan
    if slug is None:
        if ad == "public repo oluşturma":
            return f"{ad} kapalı: repoyu private kur, `{KOMUT} SAHIP/REPO` geçince aç"
        return f"{ad}: hedef repo belirlenemedi, --repo ile yaz"
    try:
        ayar = ayar or ayar_mod.yukle()
    except ayar_mod.AyarHatasi as exc:
        return f"{ad} ({slug}): {exc}"
    sebep = fis.sorun(slug, ayar_mod.fis_dizini(ayar), ayar.gecerlilik_saat * 3600, ozet_al or fis.ref_ozeti)
    return f"{ad} ({slug}): {sebep}. Önce: {KOMUT} {slug}" if sebep else None


def _metinler(arac_girdisi):
    deger = arac_girdisi.get("command")
    if isinstance(deger, list):
        deger = " ".join(str(x) for x in deger)
    return [deger] if isinstance(deger, str) else []


def kanca(ham):
    """Hook JSON metninden çıktı JSON'u (ret) ya da None (geç)."""
    try:
        veri = json.loads(ham)
    except ValueError:
        return None
    if not isinstance(veri, dict) or veri.get("tool_name") not in ARACLAR:
        return None
    girdi = veri.get("tool_input")
    if not isinstance(girdi, dict):
        return None
    cwd = veri.get("cwd") if isinstance(veri.get("cwd"), str) else None
    for metin in _metinler(girdi):
        sebep = denetle(metin, cwd)
        if sebep:
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "yayın kapısı: " + sebep,
            }}
    return None


def cli(argv=None):
    p = argparse.ArgumentParser(prog="teslim-kapi", description=__doc__.splitlines()[0])
    p.add_argument("--komut", help="hook yerine bu komutu denetle ve sonucu yaz")
    p.add_argument("--dizin", help="--komut için çalışma dizini (varsayılan: bulunulan dizin)")
    a = p.parse_args(argv)
    if a.komut is not None:
        for akis in (sys.stdout, sys.stderr):
            if hasattr(akis, "reconfigure"):
                akis.reconfigure(encoding="utf-8")
        sebep = denetle(a.komut, a.dizin or os.getcwd())
        print(f"RET: {sebep}" if sebep else "GEÇER")
        return 1 if sebep else 0
    try:
        cikti = kanca(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001  # hook ajanı kırmamalı
        return 0
    if cikti:
        sys.stdout.write(json.dumps(cikti, ensure_ascii=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(cli())
