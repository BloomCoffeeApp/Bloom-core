from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def log(
    db: Session,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Adds an audit row to the current transaction (caller commits)."""
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id, payload=payload))
