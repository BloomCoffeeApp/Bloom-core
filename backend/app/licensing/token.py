"""Signed license tokens: `BLOOM1.<base64url(json payload)>.<base64url(ed25519 signature)>`.

The signature covers `BLOOM1.<payload>`. Payload fields:
  v        format version (1)
  lid      license id
  cust     customer display name
  plan     "pro" | "trial"
  features list of feature names, or ["*"] for all
  mid      machine id the token is bound to
  iat      issued at (unix seconds)
  exp      paid/valid through (unix seconds), null = perpetual
  grace    days the token keeps working after `exp` while offline
  pkey     (optional) the subscription plan it was sold under, e.g. "pro_mensual"
"""

import base64
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.config import FROZEN

PREFIX = "BLOOM1"
_PUBLIC_KEY_FILE = Path(__file__).with_name("public_key.txt")
_public_key_override: bytes | None = None


class TokenError(ValueError):
    pass


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def set_public_key(raw: bytes | None) -> None:
    """Tests only: verify against another key."""
    global _public_key_override
    _public_key_override = raw


def public_key() -> Ed25519PublicKey:
    raw = _public_key_override
    # Development/e2e only: never honoured by the packaged app.
    if raw is None and not FROZEN and os.environ.get("BLOOM_LICENSE_PUBLIC_KEY"):
        raw = b64d(os.environ["BLOOM_LICENSE_PUBLIC_KEY"])
    if raw is None:
        try:
            raw = b64d(_PUBLIC_KEY_FILE.read_text(encoding="utf-8").strip())
        except OSError as e:
            raise TokenError("La app no tiene clave pública de licencias") from e
    return Ed25519PublicKey.from_public_bytes(raw)


def decode(token: str) -> dict:
    """Returns the payload if the signature is valid; raises TokenError otherwise."""
    try:
        prefix, payload_b64, sig_b64 = token.strip().split(".")
    except ValueError as e:
        raise TokenError("Formato de licencia inválido") from e
    if prefix != PREFIX:
        raise TokenError("Formato de licencia inválido")
    try:
        public_key().verify(b64d(sig_b64), f"{prefix}.{payload_b64}".encode())
    except (InvalidSignature, ValueError) as e:
        raise TokenError("La firma de la licencia no es válida") from e
    try:
        payload = json.loads(b64d(payload_b64))
    except ValueError as e:
        raise TokenError("Formato de licencia inválido") from e
    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise TokenError("Versión de licencia no soportada")
    return payload
