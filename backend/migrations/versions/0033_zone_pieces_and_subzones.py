"""zone pieces and sub-zones

Revision ID: 0033_zone_pieces_and_subzones
Revises: 0032_zone_areas_and_table_codes
Create Date: 2026-11-15 22:40:00

Additive: `zone_pieces` (extra rectangles of a zone, so a zone can be an L or any shape made of rectangles) and
`floor_zones.parent_id` (a sub-zone sits inside another zone and inherits its waiter).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0033_zone_pieces_and_subzones'
down_revision: Union[str, Sequence[str], None] = '0032_zone_areas_and_table_codes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'zone_pieces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zone_id', sa.Integer(), nullable=False),
        sa.Column('pos_x', sa.Integer(), nullable=False),
        sa.Column('pos_y', sa.Integer(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['zone_id'], ['floor_zones.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_zone_pieces_zone_id', 'zone_pieces', ['zone_id'], unique=False)
    with op.batch_alter_table('floor_zones', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_floor_zones_parent_id', 'floor_zones', ['parent_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('floor_zones', schema=None) as batch_op:
        batch_op.drop_constraint('fk_floor_zones_parent_id', type_='foreignkey')
        batch_op.drop_column('parent_id')
    op.drop_index('ix_zone_pieces_zone_id', table_name='zone_pieces')
    op.drop_table('zone_pieces')
