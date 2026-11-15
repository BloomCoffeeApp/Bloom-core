"""floor map items and two table shapes

Revision ID: 0030_floor_items
Revises: 0029_shifts_and_holidays
Create Date: 2026-11-15 21:00:00

Additive: `floor_items` (counter, bar, cashier, kitchen, door, bathroom, stairs, plant, wall) drawn on the floor map
as references. Tables only have two shapes now, rectangular and round: the old `square` becomes `rect` (a rectangle
with equal sides is a square), so nothing visible changes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0030_floor_items'
down_revision: Union[str, Sequence[str], None] = '0029_shifts_and_holidays'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'floor_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('label', sa.String(length=40), nullable=True),
        sa.Column('pos_x', sa.Integer(), nullable=False),
        sa.Column('pos_y', sa.Integer(), nullable=False),
        sa.Column('width', sa.Integer(), server_default='4', nullable=False),
        sa.Column('height', sa.Integer(), server_default='2', nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute("UPDATE dining_tables SET shape = 'rect' WHERE shape = 'square'")


def downgrade() -> None:
    op.drop_table('floor_items')
