"""barista tasting: aroma, cupping scores and flavor notes per shot; coffee profile and menu role

Revision ID: 0014_barista_tasting
Revises: 0013_stock_packages
Create Date: 2026-11-06 12:00:00

Purely additive (all columns nullable). `shot_logs`: `aroma` (1..5), `cupping` (JSON, 0..10 per
attribute), `flavor_notes` (JSON list of flavor wheel keys). `coffees`: `flavor_notes`,
`roast_point` (medium|high|city|full_city|french|italian), `taste_profile` (JSON 1..5) and
`menu_role` (house|decaf|origin: the coffee shown to customers).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0014_barista_tasting'
down_revision: Union[str, Sequence[str], None] = '0013_stock_packages'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('shot_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('aroma', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('cupping', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('flavor_notes', sa.JSON(), nullable=True))

    with op.batch_alter_table('coffees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('flavor_notes', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('roast_point', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('taste_profile', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('menu_role', sa.String(length=10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('coffees', schema=None) as batch_op:
        batch_op.drop_column('menu_role')
        batch_op.drop_column('taste_profile')
        batch_op.drop_column('roast_point')
        batch_op.drop_column('flavor_notes')

    with op.batch_alter_table('shot_logs', schema=None) as batch_op:
        batch_op.drop_column('flavor_notes')
        batch_op.drop_column('cupping')
        batch_op.drop_column('aroma')
