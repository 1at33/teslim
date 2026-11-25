"""Pytest: testler geliştiricinin kendi ayar, ad listesi ve fiş dizinine bağlanmasın."""
import sys
from pathlib import Path

import pytest

SRC = str(Path(__file__).resolve().parents[1] / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


@pytest.fixture(autouse=True)
def teslim_ayar_izole(monkeypatch, tmp_path):
    for ad in ("TESLIM_AYAR", "TESLIM_ADLAR", "TESLIM_FIS_DIZIN"):
        monkeypatch.delenv(ad, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    if sys.platform == "win32":
        monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
