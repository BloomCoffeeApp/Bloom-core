"""tables.send permission

Revision ID: 0034_tables_send_permission
Revises: 0033_zone_pieces_and_subzones
Create Date: 2026-11-16 09:30:00

Data only: the new permission `tables.send` ("send orders to a table from the register") is granted to every
edited or custom role that can already sell (`pos.sell`), so nobody loses what they could do before. Built-in roles
without a row get it from `app/permissions.py`.
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0034_tables_send_permission'
down_revision: Union[str, Sequence[str], None] = '0033_zone_pieces_and_subzones'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW = "tables.send"
REQUIRED = "pos.sell"


def _rewrite(add: bool) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, permissions FROM roles")).fetchall()
    for rid, raw in rows:
        perms = json.loads(raw) if isinstance(raw, str) else list(raw or [])
        if add and REQUIRED in perms and NEW not in perms:
            perms.append(NEW)
        elif not add and NEW in perms:
            perms = [p for p in perms if p != NEW]
        else:
            continue
        conn.execute(sa.text("UPDATE roles SET permissions = :p WHERE id = :i"), {"p": json.dumps(perms), "i": rid})


def upgrade() -> None:
    _rewrite(add=True)


def downgrade() -> None:
    _rewrite(add=False)
