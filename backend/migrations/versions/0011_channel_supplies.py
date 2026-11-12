"""supplies by channel ("Insumos según el canal"): stock items a sold unit consumes per channel

Revision ID: 0011_packaging_by_channel
Revises: 0010_roles_and_staff
Create Date: 2026-11-06 18:00:00

Purely additive: a new table. Empty by default: no sale consumes anything extra until the café
fills a list (per category, product or size) for salón, para llevar or delivery.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0011_packaging_by_channel'  # id kept: 0012_expenses already chains to it
down_revision: Union[str, Sequence[str], None] = '0010_roles_and_staff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('channel_supplies',
    sa.Column('product_id', sa.Integer(), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('channel', sa.String(length=10), nullable=False),
    sa.Column('size_id', sa.Integer(), nullable=True),
    sa.Column('stock_item_id', sa.Integer(), nullable=False),
    sa.Column('qty', sa.Float(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['product_categories.id'], name=op.f('fk_channel_supplies_category_id_product_categories'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_channel_supplies_product_id_products'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['size_id'], ['sizes.id'], name=op.f('fk_channel_supplies_size_id_sizes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['stock_item_id'], ['stock_items.id'], name=op.f('fk_channel_supplies_stock_item_id_stock_items'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_channel_supplies'))
    )
    with op.batch_alter_table('channel_supplies', schema=None) as batch_op:
        batch_op.create_index('ix_channel_supplies_category', ['category_id', 'channel'], unique=False)
        batch_op.create_index('ix_channel_supplies_product', ['product_id', 'channel'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('channel_supplies', schema=None) as batch_op:
        batch_op.drop_index('ix_channel_supplies_product')
        batch_op.drop_index('ix_channel_supplies_category')
    op.drop_table('channel_supplies')
