"""device info on login sessions

Revision ID: 0027_session_devices
Revises: 0026_idempotency_keys
Create Date: 2026-11-14 13:00:00

Purely additive: `user_sessions.client` ("equipo" for the staff phone app, NULL = the normal app),
`user_agent` (trimmed) and `last_seen_at`, so an admin can see and disconnect each open session.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0027_session_devices'
down_revision: Union[str, Sequence[str], None] = '0026_idempotency_keys'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('client', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('user_agent', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('last_seen_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.drop_column('last_seen_at')
        batch_op.drop_column('user_agent')
        batch_op.drop_column('client')
