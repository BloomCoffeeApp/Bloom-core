"""drink guides: step-by-step preparation guides, optionally linked to a product

Revision ID: 0002_drink_guides
Revises: a8c15fc74414
Create Date: 2026-10-30 20:51:46.769795

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_drink_guides'
down_revision: Union[str, Sequence[str], None] = 'a8c15fc74414'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('drink_guides',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('base_key', sa.String(length=60), nullable=True),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('cup', sa.String(length=80), nullable=True),
    sa.Column('serving', sa.String(length=80), nullable=True),
    sa.Column('difficulty', sa.Integer(), nullable=False),
    sa.Column('total_time_s', sa.Integer(), nullable=True),
    sa.Column('prerequisites', sa.JSON(), nullable=False),
    sa.Column('steps', sa.JSON(), nullable=False),
    sa.Column('layers', sa.JSON(), nullable=False),
    sa.Column('hot', sa.Boolean(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_drink_guides_product_id_products'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_drink_guides')),
    sa.UniqueConstraint('product_id', name=op.f('uq_drink_guides_product_id'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('drink_guides')
