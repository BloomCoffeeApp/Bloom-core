import json
import os
import sys
from pathlib import Path

APP_VERSION = "1.0.0"

FROZEN = getattr(sys, "frozen", False)
BASE_DIR = Path(sys._MEIPASS) if FROZEN else Path(__file__).resolve().parents[2]  # type: ignore[attr-defined]

# Branding lives in /brand.json (single source of truth for name, port, colors).
_BRAND_DEFAULTS = {"name": "Bloom", "appId": "bloom-cafe", "dataDirName": "Bloom", "port": 47821}
try:
    BRAND: dict = {**_BRAND_DEFAULTS, **json.loads((BASE_DIR / "brand.json").read_text(encoding="utf-8"))}
except (OSError, ValueError):
    BRAND = dict(_BRAND_DEFAULTS)

APP_NAME = BRAND["dataDirName"]
APP_DISPLAY_NAME = BRAND["name"]
APP_ID = BRAND["appId"]


def _data_dir() -> Path:
    override = os.environ.get("CAFE_DATA_DIR")
    if override:
        return Path(override)
    if FROZEN:
        return Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    return BASE_DIR / "backend"


DATA_DIR = _data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR = DATA_DIR / "backups"
UPLOAD_DIR = DATA_DIR / "uploads"
for _d in (BACKUP_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.environ.get("CAFE_DB_PATH", DATA_DIR / ("data.db" if FROZEN else "dev.db")))
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
MIGRATIONS_DIR = BASE_DIR / "backend" / "migrations"
ALEMBIC_INI = BASE_DIR / "backend" / "alembic.ini"

PORT = int(os.environ.get("CAFE_PORT", BRAND["port"]))
TIMEZONE = "America/Argentina/Buenos_Aires"
SESSION_HOURS = 16
