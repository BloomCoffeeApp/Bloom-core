"""per-user permission exceptions

Revision ID: 0025_user_permission_overrides
Revises: 0024_floor_map
Create Date: 2026-11-13 16:00:00

Purely additive: `users.perm_grants` / `users.perm_revokes` (JSON lists of permission keys) hold the
exceptions a person has on top of their role. Empty = exactly the role's permissions, as before.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0025_user_permission_overrides'
down_revision: Union[str, Sequence[str], None] = '0024_floor_map'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('perm_grants', sa.JSON(), server_default='[]', nullable=False))
        batch_op.add_column(sa.Column('perm_revokes', sa.JSON(), server_default='[]', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('perm_revokes')
        batch_op.drop_column('perm_grants')
