"""floor map

Revision ID: 0024_floor_map
Revises: 0023_tip_payouts
Create Date: 2026-11-13 12:30:00

Purely additive: where a table sits on the floor map (grid cells), its size, shape and seats.
A table without position (NULL) is not on the map yet.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0024_floor_map'
down_revision: Union[str, Sequence[str], None] = '0023_tip_payouts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('dining_tables', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pos_x', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('pos_y', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('width', sa.Integer(), server_default='4', nullable=False))
        batch_op.add_column(sa.Column('height', sa.Integer(), server_default='4', nullable=False))
        batch_op.add_column(sa.Column('shape', sa.String(length=8), server_default='square', nullable=False))
        batch_op.add_column(sa.Column('seats', sa.Integer(), server_default='4', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('dining_tables', schema=None) as batch_op:
        batch_op.drop_column('seats')
        batch_op.drop_column('shape')
        batch_op.drop_column('height')
        batch_op.drop_column('width')
        batch_op.drop_column('pos_y')
        batch_op.drop_column('pos_x')
