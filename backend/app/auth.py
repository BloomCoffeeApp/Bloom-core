import secrets
import threading
import time
from collections.abc import Callable
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import SESSION_HOURS
from app.db import get_db
from app.models import User, UserSession, utcnow

_hasher = PasswordHasher()


def hash_pin(pin: str) -> str:
    return _hasher.hash(pin)


def verify_pin(pin_hash: str, pin: str) -> bool:
    try:
        return _hasher.verify(pin_hash, pin)
    except VerifyMismatchError:
        return False


class LoginThrottle:
    """In-memory brute-force protection for 4–6 digit PINs.

    After MAX_FAILS consecutive failures for the same user (or the same client IP),
    login is blocked for a lock period that doubles on every further failure
    (30 s, 60 s, 120 s … up to 15 min). A successful login resets the counter.
    """

    MAX_FAILS = 5
    BASE_LOCK_S = 30
    MAX_LOCK_S = 15 * 60

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, tuple[int, float]] = {}  # key -> (fails, locked_until)

    def wait_seconds(self, *keys: str) -> int:
        """Seconds the caller must still wait (0 = allowed)."""
        now = time.monotonic()
        with self._lock:
            until = max((self._state.get(k, (0, 0.0))[1] for k in keys), default=0.0)
        return int(until - now) + 1 if until > now else 0

    def fail(self, *keys: str) -> None:
        now = time.monotonic()
        with self._lock:
            for k in keys:
                fails = self._state.get(k, (0, 0.0))[0] + 1
                until = 0.0
                if fails >= self.MAX_FAILS:
                    until = now + min(self.BASE_LOCK_S * 2 ** (fails - self.MAX_FAILS), self.MAX_LOCK_S)
                self._state[k] = (fails, until)

    def success(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._state.pop(k, None)

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


login_throttle = LoginThrottle()


def revoke_sessions(db: Session, user_id: int) -> None:
    """Logs a user out everywhere (PIN change, deactivation, role change). Caller commits."""
    db.execute(delete(UserSession).where(UserSession.user_id == user_id))


def create_session(db: Session, user: User) -> str:
    db.execute(delete(UserSession).where(UserSession.expires_at < utcnow()))
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(token=token, user_id=user.id, expires_at=utcnow() + timedelta(hours=SESSION_HOURS))
    )
    user.last_login_at = utcnow()
    db.commit()
    return token


def get_current_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión no iniciada")
    token = authorization.removeprefix("Bearer ").strip()
    sess = db.scalar(select(UserSession).where(UserSession.token == token))
    if not sess or sess.expires_at < utcnow():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión vencida")
    user = db.get(User, sess.user_id)
    if not user or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inactivo")
    return user


def require_role(*roles: str) -> Callable[..., User]:
    """Dependency: admin always passes; otherwise the user's role must be listed."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role != "admin" and user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tenés permiso para esta acción")
        return user

    return _dep


CurrentUser = Depends(get_current_user)
Manager = Depends(require_role("encargado"))
AdminOnly = Depends(require_role())
