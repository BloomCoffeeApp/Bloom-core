"""Internal notice board and opening/closing checklists."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Checklist, ChecklistItem, ChecklistRun, ChecklistRunItem, Notice, User, utcnow
from app.services import audit
from app.services.timeutil import day_bounds_utc, local_today, to_utc_naive

# ---------------------------------------------------------------- notices


def _naive_utc(dt):
    return to_utc_naive(dt) if dt is not None and dt.tzinfo is not None else dt


def notice_out(db: Session, n: Notice, names: dict[int, str] | None = None) -> dict[str, Any]:
    if names is None:
        author = db.get(User, n.author_id) if n.author_id else None
        name = author.name if author else None
    else:
        name = names.get(n.author_id) if n.author_id else None
    return {
        "id": n.id, "title": n.title, "body": n.body, "pinned": n.pinned, "color": n.color,
        "expires_at": n.expires_at, "author_id": n.author_id, "author_name": name,
        "created_at": n.created_at, "updated_at": n.updated_at,
        "expired": bool(n.expires_at and n.expires_at < utcnow()),
    }


def list_notices(db: Session, include_expired: bool = False) -> list[dict[str, Any]]:
    stmt = select(Notice)
    if not include_expired:
        stmt = stmt.where(or_(Notice.expires_at.is_(None), Notice.expires_at >= utcnow()))
    notices = list(db.scalars(stmt.order_by(Notice.pinned.desc(), Notice.created_at.desc(), Notice.id.desc())))
    names = {u.id: u.name for u in db.scalars(select(User))}
    return [notice_out(db, n, names) for n in notices]


def get_notice(db: Session, notice_id: int) -> Notice:
    n = db.get(Notice, notice_id)
    if n is None:
        raise HTTPException(404, "Aviso no encontrado")
    return n


def create_notice(db: Session, data: dict[str, Any], user: User) -> dict[str, Any]:
    data["expires_at"] = _naive_utc(data.get("expires_at"))
    n = Notice(author_id=user.id, **data)
    db.add(n)
    db.flush()
    audit.log(db, user.id, "create", "notice", n.id, {"title": n.title})
    db.commit()
    db.refresh(n)
    return notice_out(db, n)


def update_notice(db: Session, n: Notice, data: dict[str, Any], user: User) -> dict[str, Any]:
    if "expires_at" in data:
        data["expires_at"] = _naive_utc(data["expires_at"])
    for k, v in data.items():
        setattr(n, k, v)
    audit.log(db, user.id, "update", "notice", n.id, {"title": n.title})
    db.commit()
    db.refresh(n)
    return notice_out(db, n)


def delete_notice(db: Session, n: Notice, user: User) -> None:
    audit.log(db, user.id, "delete", "notice", n.id, {"title": n.title})
    db.delete(n)
    db.commit()


# ---------------------------------------------------------------- checklists


def get_checklist(db: Session, checklist_id: int) -> Checklist:
    c = db.get(Checklist, checklist_id)
    if c is None:
        raise HTTPException(404, "Checklist no encontrado")
    return c


def list_checklists(db: Session, include_inactive: bool = True) -> list[Checklist]:
    stmt = select(Checklist)
    if not include_inactive:
        stmt = stmt.where(Checklist.active.is_(True))
    return list(db.scalars(stmt.order_by(Checklist.active.desc(), Checklist.kind, Checklist.name)))


def _sync_items(c: Checklist, items: list[dict[str, Any]]) -> None:
    by_id = {it.id: it for it in c.items}
    new_list: list[ChecklistItem] = []
    for i, data in enumerate(items):
        text = data["text"].strip()
        if not text:
            continue
        it = by_id.get(data.get("id") or 0)
        if it is None:
            it = ChecklistItem(text=text, sort_order=i)
        else:
            it.text, it.sort_order = text, i
        new_list.append(it)
    c.items = new_list


def create_checklist(db: Session, data: dict[str, Any], user: User) -> Checklist:
    c = Checklist(name=data["name"].strip(), kind=data.get("kind", "custom"))
    _sync_items(c, data.get("items", []))
    db.add(c)
    db.flush()
    audit.log(db, user.id, "create", "checklist", c.id, {"name": c.name})
    db.commit()
    db.refresh(c)
    return c


def update_checklist(db: Session, c: Checklist, data: dict[str, Any], user: User) -> Checklist:
    items = data.pop("items", None)
    for k, v in data.items():
        setattr(c, k, v)
    if items is not None:
        _sync_items(c, items)
    audit.log(db, user.id, "update", "checklist", c.id, {"name": c.name})
    db.commit()
    db.refresh(c)
    return c


def _today_run(db: Session, checklist_id: int) -> ChecklistRun | None:
    start, end = day_bounds_utc(local_today())
    return db.scalar(
        select(ChecklistRun)
        .where(ChecklistRun.checklist_id == checklist_id, ChecklistRun.started_at >= start, ChecklistRun.started_at < end)
        .order_by(ChecklistRun.id)
    )


def _ensure_run_items(c: Checklist, run: ChecklistRun) -> None:
    """Adds run items for checklist items created after the run started."""
    have = {ri.item_id for ri in run.items}
    for it in c.items:
        if it.id not in have:
            run.items.append(ChecklistRunItem(item_id=it.id))


def _refresh_completed(c: Checklist, run: ChecklistRun) -> None:
    current = {it.id for it in c.items}
    relevant = [ri for ri in run.items if ri.item_id in current]
    if relevant and all(ri.done for ri in relevant):
        if run.completed_at is None:
            run.completed_at = utcnow()
    else:
        run.completed_at = None


def start_run(db: Session, c: Checklist, user: User) -> ChecklistRun:
    if not c.active:
        raise HTTPException(400, "El checklist está desactivado")
    run = _today_run(db, c.id)
    if run is None:
        run = ChecklistRun(checklist_id=c.id, user_id=user.id, started_at=utcnow())
        db.add(run)
    _ensure_run_items(c, run)
    _refresh_completed(c, run)
    db.commit()
    db.refresh(run)
    return run


def toggle_run_item(db: Session, run_id: int, item_id: int, done: bool, user: User) -> ChecklistRun:
    run = db.get(ChecklistRun, run_id)
    if run is None:
        raise HTTPException(404, "Corrida de checklist no encontrada")
    c = get_checklist(db, run.checklist_id)
    _ensure_run_items(c, run)
    ri = next((r for r in run.items if r.item_id == item_id), None)
    if ri is None:
        raise HTTPException(404, "Ítem no encontrado en el checklist")
    if ri.done != done:
        ri.done = done
        ri.done_by = user.id if done else None
        ri.done_at = utcnow() if done else None
    _refresh_completed(c, run)
    db.commit()
    db.refresh(run)
    return run


def run_out(db: Session, c: Checklist, run: ChecklistRun | None, names: dict[int, str]) -> dict[str, Any]:
    state = {ri.item_id: ri for ri in run.items} if run else {}
    items = []
    for it in c.items:
        ri = state.get(it.id)
        items.append({
            "item_id": it.id,
            "text": it.text,
            "done": bool(ri and ri.done),
            "done_by": ri.done_by if ri else None,
            "done_by_name": names.get(ri.done_by) if ri and ri.done_by else None,
            "done_at": ri.done_at if ri else None,
        })
    return {
        "checklist_id": c.id,
        "name": c.name,
        "kind": c.kind,
        "run_id": run.id if run else None,
        "started_at": run.started_at if run else None,
        "started_by_name": names.get(run.user_id) if run and run.user_id else None,
        "completed_at": run.completed_at if run else None,
        "done": sum(1 for i in items if i["done"]),
        "total": len(items),
        "items": items,
    }


def user_names(db: Session) -> dict[int, str]:
    return {u.id: u.name for u in db.scalars(select(User))}


KIND_ORDER = {"opening": 0, "closing": 1, "custom": 2}


def today(db: Session) -> list[dict[str, Any]]:
    names = user_names(db)
    lists = sorted(list_checklists(db, include_inactive=False), key=lambda c: (KIND_ORDER.get(c.kind, 9), c.name))
    return [run_out(db, c, _today_run(db, c.id), names) for c in lists]
