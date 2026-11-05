"""Third-party license notices (Configuración → Acerca de → Licencias de terceros).

The file is generated at build time by build/third_party_notices.py and bundled next to brand.json in
the .exe. From source it is read from build/generated/ if someone ran the script; otherwise the screen
says it is generated with the installer.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import BASE_DIR, FROZEN

FILE_NAME = "third_party_notices.json"


def notices_path() -> Path:
    return BASE_DIR / FILE_NAME if FROZEN else BASE_DIR / "build" / "generated" / FILE_NAME


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> dict[str, Any]:  # noqa: ARG001 (mtime busts the cache)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def notices() -> dict[str, Any]:
    path = notices_path()
    try:
        data = _load(str(path), path.stat().st_mtime)
    except (OSError, ValueError):
        return {"available": False, "generated_at": None, "packages": []}
    packages = [
        {
            "name": str(p.get("name", "")),
            "version": str(p.get("version", "")),
            "license": str(p.get("license", "")),
            "source": str(p.get("source", "")),
            "homepage": str(p.get("homepage", "")),
            "copyright": [str(c) for c in p.get("copyright", [])],
            "text": str(p.get("text", "")),
            "note": str(p.get("note", "")),
        }
        for p in data.get("packages", [])
    ]
    packages.sort(key=lambda p: p["name"].lower())
    return {"available": True, "generated_at": data.get("generated_at"), "packages": packages}
