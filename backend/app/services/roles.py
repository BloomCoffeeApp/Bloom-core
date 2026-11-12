"""Roles and permissions: what each user may do (catalog in `app/permissions.py`).

- `admin` always has everything and can't be edited or deleted.
- Built-in roles (encargado, cajero, barista) start with their historical permissions; the owner can
  edit them (a `roles` row then overrides the defaults) and reset them.
- Custom roles are rows with `builtin = False`; a role in use can't be deleted.
- A non-admin with `users.manage` can only hand out roles whose permissions are a subset of their own,
  and never touch admins (no privilege escalation).
"""

import re
import unicodedata
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

from app.models import Role, User
from app.permissions import ADMIN, ALL, BUILTIN_ROLES, PERMISSIONS, REQUIRES, normalize
from app.services import audit

_CACHE_ATTR = "_bloom_permissions"


def _row(db: Session, key: str) -> Role | None:
    return db.scalar(select(Role).where(Role.key == key))


def permissions_for_role(db: Session | None, key: str) -> frozenset[str]:
    if key == ADMIN:
        return ALL
    row = _row(db, key) if db is not None else None
    if row is not None:
        return normalize(row.permissions or [])
    builtin = BUILTIN_ROLES.get(key)
    return builtin["permissions"] if builtin else frozenset()


def permissions_of(user: User) -> frozenset[str]:
    """The user's permissions, computed once per loaded instance (= once per request)."""
    cached = user.__dict__.get(_CACHE_ATTR)
    if cached is None:
        cached = permissions_for_role(object_session(user), user.role)
        user.__dict__[_CACHE_ATTR] = cached
    return cached


def has(user: User, *perms: str) -> bool:
    """True when the user is admin or has any of `perms`."""
    if user.role == ADMIN:
        return True
    mine = permissions_of(user)
    return any(p in mine for p in perms)


def role_name(db: Session, key: str) -> str:
    row = _row(db, key)
    if row is not None:
        return row.name
    return BUILTIN_ROLES.get(key, {}).get("name", key)


def names(db: Session) -> dict[str, str]:
    out = {k: v["name"] for k, v in BUILTIN_ROLES.items()}
    out.update({r.key: r.name for r in db.scalars(select(Role))})
    return out


def exists(db: Session, key: str) -> bool:
    return key in BUILTIN_ROLES or _row(db, key) is not None


# ---------------------------------------------------------------- listing


def catalog() -> list[dict[str, str]]:
    return [
        {"key": k, "group": g, "label": label, "description": d, "requires": REQUIRES.get(k)}
        for k, (g, label, d) in PERMISSIONS.items()
    ]


def list_roles(db: Session) -> list[dict[str, Any]]:
    counts = dict(
        db.execute(select(User.role, func.count(User.id)).where(User.active.is_(True)).group_by(User.role)).all()
    )
    rows = {r.key: r for r in db.scalars(select(Role).order_by(Role.id))}
    out = []
    for key, b in BUILTIN_ROLES.items():
        row = rows.pop(key, None)
        perms = ALL if key == ADMIN else (normalize(row.permissions or []) if row else b["permissions"])
        out.append({
            "key": key, "name": row.name if row else b["name"], "hint": b["hint"], "builtin": True,
            "editable": key != ADMIN, "customized": row is not None and perms != b["permissions"],
            "permissions": sorted(perms), "users": counts.get(key, 0),
        })
    for key, row in rows.items():
        out.append({
            "key": key, "name": row.name, "hint": None, "builtin": False, "editable": True, "customized": False,
            "permissions": sorted(normalize(row.permissions or [])), "users": counts.get(key, 0),
        })
    return out


def get(db: Session, key: str) -> dict[str, Any]:
    for r in list_roles(db):
        if r["key"] == key:
            return r
    raise HTTPException(404, "Rol inexistente")


# ---------------------------------------------------------------- editing (admin only)


def _slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:16] or "rol"


def _clean_name(db: Session, name: str, exclude_key: str | None = None) -> str:
    name = " ".join(name.split())
    if not name:
        raise HTTPException(400, "El nombre es obligatorio")
    taken = {k: v for k, v in names(db).items() if k != exclude_key}
    if name.casefold() in {v.casefold() for v in taken.values()}:
        raise HTTPException(409, f"Ya existe un rol «{name}»")
    return name


def _check_perms(perms: list[str]) -> frozenset[str]:
    unknown = [p for p in perms if p not in PERMISSIONS]
    if unknown:
        raise HTTPException(400, f"Permiso desconocido: {', '.join(unknown)}")
    return normalize(perms)


def create(db: Session, name: str, perms: list[str], me: User) -> dict[str, Any]:
    name = _clean_name(db, name)
    clean = _check_perms(perms)
    base, key, n = _slug(name), _slug(name), 2
    while exists(db, key) or key == ADMIN:
        suffix = f"_{n}"
        key, n = base[: 20 - len(suffix)] + suffix, n + 1
    db.add(Role(key=key, name=name, permissions=sorted(clean), builtin=False))
    audit.log(db, me.id, "create", "role", None, {"key": key, "name": name, "permissions": sorted(clean)})
    db.commit()
    return get(db, key)


def update(db: Session, key: str, name: str | None, perms: list[str] | None, me: User) -> dict[str, Any]:
    if key == ADMIN:
        raise HTTPException(400, "El rol Administrador siempre tiene acceso total y no se puede editar")
    if not exists(db, key):
        raise HTTPException(404, "Rol inexistente")
    before = get(db, key)
    row = _row(db, key)
    if row is None:  # first edit of a built-in role: materialize its defaults
        b = BUILTIN_ROLES[key]
        row = Role(key=key, name=b["name"], permissions=sorted(b["permissions"]), builtin=True)
        db.add(row)
        db.flush()
    if name is not None:
        row.name = _clean_name(db, name, exclude_key=key)
    if perms is not None:
        row.permissions = sorted(_check_perms(perms))
    audit.log(db, me.id, "update", "role", row.id, {
        "key": key,
        "name": [before["name"], row.name] if before["name"] != row.name else None,
        "added": sorted(set(row.permissions) - set(before["permissions"])),
        "removed": sorted(set(before["permissions"]) - set(row.permissions)),
    })
    db.commit()
    return get(db, key)


def reset(db: Session, key: str, me: User) -> dict[str, Any]:
    if key not in BUILTIN_ROLES or key == ADMIN:
        raise HTTPException(400, "Solo los roles de fábrica se pueden restablecer")
    row = _row(db, key)
    if row is not None:
        db.delete(row)
        audit.log(db, me.id, "reset", "role", row.id, {"key": key})
        db.commit()
    return get(db, key)


def delete(db: Session, key: str, me: User) -> None:
    if key in BUILTIN_ROLES:
        raise HTTPException(400, "Los roles de fábrica no se pueden borrar")
    row = _row(db, key)
    if row is None:
        raise HTTPException(404, "Rol inexistente")
    used = db.scalar(select(func.count(User.id)).where(User.role == key)) or 0
    if used:
        raise HTTPException(409, f"Hay {used} usuario(s) con este rol: cambiales el rol antes de borrarlo")
    db.delete(row)
    audit.log(db, me.id, "delete", "role", row.id, {"key": key, "name": row.name})
    db.commit()


# ---------------------------------------------------------------- user management guard


def check_can_assign(db: Session, me: User, role_key: str, target: User | None = None) -> None:
    """Raises unless `me` may give `role_key` (and edit `target`). Admins may do anything."""
    if not exists(db, role_key):
        raise HTTPException(400, "Rol inexistente")
    if me.role == ADMIN:
        return
    if role_key == ADMIN or (target is not None and target.role == ADMIN):
        raise HTTPException(403, "Solo un administrador puede gestionar administradores")
    if not permissions_for_role(db, role_key) <= permissions_of(me):
        raise HTTPException(403, "No podés asignar un rol con más permisos que el tuyo")
    if target is not None and not permissions_for_role(db, target.role) <= permissions_of(me):
        raise HTTPException(403, "No podés editar a un usuario con más permisos que vos")
