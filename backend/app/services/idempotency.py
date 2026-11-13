"""Idempotency for requests that move money: the same operation sent twice (double click, a retry after a
timeout, a flaky tablet connection) must create ONE sale / movement / payment.

The client sends `Idempotency-Key: <random id>` with the request and keeps the SAME key for a retry of the same
operation. The server remembers (key -> what it created) in the SAME transaction as the resource, so there is no
window where one exists without the other, and takes the write lock first so two simultaneous requests with the
same key are serialized: the second one finds the first one's row and returns its result."""
import hashlib
import json
import re
from datetime import timedelta

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db import lock_writes
from app.models import IdempotencyKey, User
from app.models.base import utcnow

KEY_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
RETENTION = timedelta(days=7)


def clean_key(raw: str | None) -> str | None:
    """None when the client sent no key (the request then behaves as before)."""
    if raw is None or raw == "":
        return None
    if not KEY_RE.match(raw):
        raise HTTPException(400, "Idempotency-Key inválida: usá entre 16 y 64 letras, números, guion o guion bajo")
    return raw


def body_hash(payload: BaseModel | dict) -> str:
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def find(db: Session, key: str, scope: str, user: User, payload_hash: str) -> int | None:
    """The id of what this key already created, or None if it is new. Takes the write lock (released at commit)."""
    lock_writes(db)
    row = db.get(IdempotencyKey, key)
    if row is None:
        return None
    if row.scope != scope or row.user_id != user.id or row.body_hash != payload_hash:
        raise HTTPException(409, "Esa clave de operación ya se usó para otro pedido distinto: generá una nueva")
    return row.resource_id


def record(db: Session, key: str, scope: str, user: User, payload_hash: str, resource_id: int) -> None:
    """Call it before the commit that saves the resource: both land together or neither does."""
    db.add(IdempotencyKey(key=key, scope=scope, user_id=user.id, body_hash=payload_hash, resource_id=resource_id))
    db.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < utcnow() - RETENTION))
