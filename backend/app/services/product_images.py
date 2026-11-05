"""Product photos: validated, re-encoded and downsized server-side, stored in the uploads dir.

The upload is decoded with Pillow (never trusted by extension or Content-Type), orientation is
fixed from EXIF, it is resized to at most MAX_SIDE px and re-encoded as WebP — which also drops
any metadata (GPS, camera). Files live in `<uploads>/products/` and are served at `/uploads/...`.
"""

import io
import secrets
import warnings
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.config import UPLOAD_DIR
from app.models import Product, User
from app.services import audit

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "MPO"}  # MPO = JPEG from some phones
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000  # decompression-bomb guard (e.g. 8000x5000)
MAX_SIDE = 1200
THUMB_SIDE = 240
SUBDIR = "products"


def _dir() -> Path:
    d = UPLOAD_DIR / SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve(rel: str | None) -> Path | None:
    """Absolute path of a stored photo, only if it is inside <uploads>/products (no traversal)."""
    if not rel:
        return None
    base = _dir().resolve()
    path = (UPLOAD_DIR / rel).resolve()
    return path if base in path.parents else None


def _open(raw: bytes) -> Image.Image:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            img = Image.open(io.BytesIO(raw))
            if img.format not in ALLOWED_FORMATS:
                raise HTTPException(415, "Formato no soportado: subí una foto JPG, PNG o WebP")
            if img.width * img.height > MAX_PIXELS:
                raise HTTPException(413, "La foto tiene demasiada resolución")
            img.load()
        except HTTPException:
            raise
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as e:
            raise HTTPException(415, "El archivo no es una imagen válida") from e
    return img


def _encode(img: Image.Image, side: int, quality: int) -> bytes:
    img = ImageOps.exif_transpose(img)
    img.thumbnail((side, side), Image.Resampling.LANCZOS)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() or img.mode == "P" else "RGB")
    out = io.BytesIO()
    img.save(out, "WEBP", quality=quality, method=4)
    return out.getvalue()


def _delete_files(rel: str | None) -> None:
    path = _resolve(rel)
    if path is None:
        return
    path.unlink(missing_ok=True)
    (path.parent / "thumbs" / path.name).unlink(missing_ok=True)


def save_photo(db: Session, product_id: int, raw: bytes, content_type: str | None, user: User) -> Product:
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Producto no encontrado")
    from app.services import free_plan

    free_plan.ensure_usable(db, "products", p.id, p.name)
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in ALLOWED_TYPES:
        raise HTTPException(415, "Formato no soportado: subí una foto JPG, PNG o WebP")
    if not raw:
        raise HTTPException(400, "No llegó ninguna foto")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "La foto pesa demasiado (máximo 8 MB)")
    data = _encode(_open(raw), MAX_SIDE, 82)
    name = f"p{p.id}-{secrets.token_hex(4)}.webp"  # new name each time: no stale browser cache
    (_dir() / name).write_bytes(data)
    old = p.image_path
    p.image_path = f"{SUBDIR}/{name}"
    audit.log(db, user.id, "photo", "product", p.id, {"bytes": len(data)})
    db.commit()
    if old and old != p.image_path:
        _delete_files(old)
    return p


def delete_photo(db: Session, product_id: int, user: User) -> Product:
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Producto no encontrado")
    old = p.image_path
    p.image_path = None
    audit.log(db, user.id, "photo_delete", "product", p.id, {})
    db.commit()
    _delete_files(old)
    return p


def thumbnail_bytes(rel: str | None) -> bytes | None:
    """Small WebP of a stored photo (cached on disk), for the online menu snapshot. None if missing."""
    path = _resolve(rel)
    if path is None or not path.is_file():
        return None
    thumb = path.parent / "thumbs" / path.name
    if thumb.is_file():
        return thumb.read_bytes()
    try:
        with Image.open(path) as img:
            data = _encode(img, THUMB_SIDE, 60)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    thumb.parent.mkdir(exist_ok=True)
    thumb.write_bytes(data)
    return data
