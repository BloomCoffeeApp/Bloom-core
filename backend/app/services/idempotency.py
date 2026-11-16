"""Idempotency for requests that move money: the same operation sent twice (double click, a retry after a
timeout, a flaky tablet connection) must create ONE sale / movement / payment.

The client sends `Idempotency-Key: <random id>` with the request and keeps the SAME key for a retry of the same
operation. The server remembers (key -> what it created) in the SAME transaction as the resource, so there is no
window where one exists without the other, and takes the write lock first so two simultaneous requests with the
same key are serialized: the second one finds the first one's row and returns its result."""
import hashlib
import json
import re
from collections.abc import Callable
from datetime import timedelta
from typing import TypeVar

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db import lock_writes
from app.models import IdempotencyKey, User
from app.models.base import utcnow

T = TypeVar("T")
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


KeyHash = tuple[str, str]  # (Idempotency-Key, hash of the request body) handed to the service that commits


def record_if(db: Session, key: KeyHash | None, scope: str, user: User, resource_id: int) -> None:
    """`record` for services that take an optional `_key`: nothing to do when the client sent no key."""
    if key is not None:
        record(db, key[0], scope, user, key[1], resource_id)


def once(db: Session, key: str | None, scope: str, user: User, payload: BaseModel | dict,
         run: Callable[[KeyHash | None], T], load: Callable[[int], T]) -> tuple[T, bool]:
    """Runs an operation at most once per key. `run(key_hash)` does the work and must pass `key_hash` to
    `record_if(...)` before its commit; `load(id)` returns what a previous run created. Second value True = a repeat
    (nothing was done again). Without a key it is just `run(None)`, as before."""
    if key is None:
        return run(None), False
    h = body_hash(payload)
    done = find(db, key, scope, user, h)
    if done is not None:
        db.rollback()  # releases the write lock taken by `find`
        return load(done), True
    return run((key, h)), False
