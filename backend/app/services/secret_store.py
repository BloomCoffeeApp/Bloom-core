"""Encryption at rest for per-cafe credentials (e.g. the cafe's Mercado Pago access/refresh tokens).

Ciphertexts are stored in the `settings` table (so they travel inside backups/copies of the database),
never the plain values:

- **Windows (the desktop app): DPAPI** (`CryptProtectData`, user scope, via ctypes — no pywin32). The key
  is managed by Windows and bound to the logged-in Windows user of this PC: a copied database, a backup
  or a stolen disk image without that user's login can't be decrypted. Trade-off: restoring a backup on
  another PC/user means connecting Mercado Pago again (the app says so) — acceptable for a token that can
  be re-issued in one click.
- **Elsewhere (dev on Linux/macOS, the online demo, CI): Fernet** (AES-128-CBC + HMAC-SHA256) with a random
  key in `<data dir>/secret.key`, created with mode 0600 (owner-only). The key file lives next to the
  database but is NOT copied into backups (`services/backup.py` copies only the .db), so a backup alone
  doesn't reveal the secrets.

Format: "<scheme>:v1:<payload>". `decrypt` raises SecretStoreError on tampering or a foreign key/user.
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

from app.config import DATA_DIR

# Bound into DPAPI as optional entropy: other apps of the same Windows user can't decrypt by accident.
_ENTROPY = b"bloom-collect-v1"


class SecretStoreError(Exception):
    pass


def _use_dpapi() -> bool:
    return sys.platform == "win32" and os.environ.get("BLOOM_SECRET_BACKEND", "") != "file"


# ---------------------------------------------------------------- DPAPI (Windows)


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(b: bytes) -> tuple[Blob, ctypes.Array]:
        buf = ctypes.create_string_buffer(b, len(b))
        return Blob(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    src, _keep = blob(data)
    ent, _keep2 = blob(_ENTROPY)
    out = Blob()
    flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_wchar_p, ctypes.POINTER(Blob), ctypes.c_void_p,
                   ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if protect:
        ok = fn(ctypes.byref(src), "Bloom", ctypes.byref(ent), None, None, flags, ctypes.byref(out))
    else:
        ok = fn(ctypes.byref(src), None, ctypes.byref(ent), None, None, flags, ctypes.byref(out))
    if not ok:
        raise SecretStoreError("No se pudo descifrar la credencial guardada (¿otra PC u otro usuario de Windows?).")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


# ---------------------------------------------------------------- key file (other platforms)


def key_path() -> Path:
    return Path(os.environ.get("BLOOM_SECRET_KEY_FILE") or DATA_DIR / "secret.key")


def _fernet():
    from cryptography.fernet import Fernet

    path = key_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        # O_EXCL: two processes racing never overwrite each other's key; 0600 = owner only.
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as f:
                f.write(key)
    return Fernet(path.read_bytes().strip())


# ---------------------------------------------------------------- API


def encrypt(plain: str) -> str:
    data = plain.encode("utf-8")
    if _use_dpapi():
        return "dpapi:v1:" + base64.b64encode(_dpapi(data, True)).decode()
    return "fernet:v1:" + _fernet().encrypt(data).decode()


def decrypt(stored: str) -> str:
    scheme, _, rest = stored.partition(":v1:")
    try:
        if scheme == "dpapi":
            if sys.platform != "win32":
                raise SecretStoreError("Esta credencial se guardó en otra computadora: conectá de nuevo.")
            return _dpapi(base64.b64decode(rest), False).decode("utf-8")
        if scheme == "fernet":
            return _fernet().decrypt(rest.encode()).decode("utf-8")
    except SecretStoreError:
        raise
    except Exception as e:
        raise SecretStoreError("No se pudo descifrar la credencial guardada: conectá de nuevo.") from e
    raise SecretStoreError("Formato de credencial desconocido.")
