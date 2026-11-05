"""drink guides: tips, variations, equipment, origin, caffeine, featured; per-user favorites

Revision ID: 0008_drink_guide_extras
Revises: 0007_hot_query_indexes
Create Date: 2026-11-05 18:00:00

Purely additive. Existing guides get empty lists, NULL origin/caffeine and featured = false.
`drink_guide_favorites` keeps each user's favorite guides as `classic:<key>` / `guide:<id>`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008_drink_guide_extras'
down_revision: Union[str, Sequence[str], None] = '0007_hot_query_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('drink_guides', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tips', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('variations', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('equipment', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('origin', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('caffeine', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('featured', sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table('drink_guide_favorites',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('ref', sa.String(length=80), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_drink_guide_favorites_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_drink_guide_favorites')),
    sa.UniqueConstraint('user_id', 'ref', name=op.f('uq_drink_guide_favorites_user_id'))
    )
    with op.batch_alter_table('drink_guide_favorites', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_drink_guide_favorites_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('drink_guide_favorites', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_drink_guide_favorites_user_id'))
    op.drop_table('drink_guide_favorites')

    with op.batch_alter_table('drink_guides', schema=None) as batch_op:
        batch_op.drop_column('featured')
        batch_op.drop_column('caffeine')
        batch_op.drop_column('origin')
        batch_op.drop_column('equipment')
        batch_op.drop_column('variations')
        batch_op.drop_column('tips')
