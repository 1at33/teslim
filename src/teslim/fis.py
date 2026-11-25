"""Son teslim fişi: kontrol geçince yazılır, yayın kapısı okur.

Fiş repo başına bir JSON dosyasıdır: repo adı, tüm ref'lerin özeti, kontrol edilen commit ve zaman. Fiş,
süresi dolunca ya da repodaki herhangi bir dal, tag veya PR ucu değişince geçersizdir.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time

from teslim import ayar as ayar_mod

SLUG = re.compile(r"^[\w.-]+/[\w.-]+$")


def ref_ozeti(slug, zaman=60):
    """Tüm dal, tag ve PR uçlarının özeti; push olunca değişir. Okunamazsa OSError."""
    try:
        r = subprocess.run(["git", "ls-remote", f"https://github.com/{slug}.git"], capture_output=True,
                           check=False, timeout=zaman)
    except subprocess.TimeoutExpired as exc:
        raise OSError("ls-remote zaman aşımı") from exc
    if r.returncode:
        raise OSError("ls-remote başarısız")
    ham = r.stdout.decode("utf-8", "replace")
    return hashlib.sha256("\n".join(sorted(s.strip() for s in ham.splitlines() if s.strip())).encode()).hexdigest()


def fis_yolu(slug, dizin=None):
    if dizin is None:
        dizin = ayar_mod.fis_dizini(ayar_mod.yukle())
    return dizin / (slug.replace("/", "__").casefold() + ".json")


def yaz(slug, ozet, sha, dizin):
    dizin.mkdir(parents=True, exist_ok=True)
    kayit = {"repo": slug, "ref_ozeti": ozet, "sha": sha, "zaman": time.time()}
    fis_yolu(slug, dizin).write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")


def sorun(slug, dizin, gecerlilik_sn, ozet_al=ref_ozeti):
    """Fiş geçerliyse None, değilse sebep."""
    try:
        kayit = json.loads(fis_yolu(slug, dizin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "fiş yok"
    if not isinstance(kayit, dict) or str(kayit.get("repo", slug)).casefold() != slug.casefold():
        return "fiş yok"
    try:
        zaman = float(kayit.get("zaman", 0))
    except (TypeError, ValueError):
        return "fiş yok"
    if not 0 <= time.time() - zaman <= gecerlilik_sn:
        return "fişin süresi dolmuş"
    try:
        if ozet_al(slug) != kayit.get("ref_ozeti"):
            return "repo fişten sonra değişmiş"
    except (OSError, subprocess.TimeoutExpired):
        return "repo durumu okunamadı"
    return None
