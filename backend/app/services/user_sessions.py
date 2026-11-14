"""Open login sessions per person: list them, disconnect one, close all but the current one.

`UserSession` rows are created by `auth.create_session`; the token is the secret and never leaves the server
(these helpers only expose the row id).
"""
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import User, UserSession, utcnow
from app.services import audit, roles


def list_for(db: Session, user_id: int, current_token: str | None = None) -> list[dict]:
    rows = db.scalars(
        select(UserSession).where(UserSession.user_id == user_id, UserSession.expires_at > utcnow())
        .order_by(UserSession.last_seen_at.desc().nulls_last(), UserSession.id.desc())
    )
    return [
        {"id": r.id, "client": r.client, "user_agent": r.user_agent, "created_at": r.created_at,
         "last_seen_at": r.last_seen_at, "expires_at": r.expires_at,
         "current": bool(current_token) and r.token == current_token}
        for r in rows
    ]


def _check_target(db: Session, me: User, target: User) -> None:
    """Disconnecting somebody else needs the same rank as editing them (never an admin, nobody above you)."""
    if me.id == target.id:
        return
    roles.check_can_assign(db, me, target.role, target=target)


def disconnect(db: Session, me: User, user_id: int, session_id: int) -> None:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "Usuario no encontrado")
    _check_target(db, me, target)
    sess = db.get(UserSession, session_id)
    if sess is None or sess.user_id != user_id:
        raise HTTPException(404, "Sesión no encontrada")
    db.delete(sess)
    audit.log(db, me.id, "disconnect", "user_session", session_id, {"user_id": user_id, "client": sess.client})
    db.commit()


def disconnect_others(db: Session, me: User, current_token: str) -> int:
    res = db.execute(delete(UserSession).where(UserSession.user_id == me.id, UserSession.token != current_token))
    audit.log(db, me.id, "disconnect_others", "user", me.id, {"count": res.rowcount})
    db.commit()
    return int(res.rowcount or 0)
