"""floors of the premises

Revision ID: 0031_floors
Revises: 0030_floor_items
Create Date: 2026-11-15 21:30:00

Additive: `floors` (basement, ground floor, first floor…) and a `floor_id` on tables and floor-map references.
Everything that exists goes to a first floor called «Planta baja» (id 1).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0031_floors'
down_revision: Union[str, Sequence[str], None] = '0030_floor_items'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'floors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=40), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute("INSERT INTO floors (id, name, sort_order) VALUES (1, 'Planta baja', 0)")
    for table in ('dining_tables', 'floor_items'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('floor_id', sa.Integer(), server_default='1', nullable=False))
            batch_op.create_index(f'ix_{table}_floor_id', ['floor_id'], unique=False)


def downgrade() -> None:
    for table in ('dining_tables', 'floor_items'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(f'ix_{table}_floor_id')
            batch_op.drop_column('floor_id')
    op.drop_table('floors')
