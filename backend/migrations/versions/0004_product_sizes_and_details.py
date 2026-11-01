"""product sizes (own price + recipe per size) and customer-facing product details

Revision ID: 0004_product_sizes_and_details
Revises: 0003_sale_courtesy
Create Date: 2026-10-31 18:00:00

Purely additive: existing products keep no sizes (single price/recipe, exactly as before) and
existing sale items keep size_id/size_name NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004_product_sizes_and_details'
down_revision: Union[str, Sequence[str], None] = '0003_sale_courtesy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('sizes',
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('short_label', sa.String(length=12), nullable=False),
    sa.Column('volume_ml', sa.Integer(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sizes'))
    )
    op.create_table('product_sizes',
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('size_id', sa.Integer(), nullable=False),
    sa.Column('price_cents', sa.Integer(), nullable=False),
    sa.Column('recipe_scale', sa.Float(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_product_sizes_product_id_products'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['size_id'], ['sizes.id'], name=op.f('fk_product_sizes_size_id_sizes')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product_sizes')),
    sa.UniqueConstraint('product_id', 'size_id', name=op.f('uq_product_sizes_product_id'))
    )
    with op.batch_alter_table('product_sizes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_product_sizes_product_id'), ['product_id'], unique=False)
    op.create_table('product_size_recipe_items',
    sa.Column('product_size_id', sa.Integer(), nullable=False),
    sa.Column('stock_item_id', sa.Integer(), nullable=False),
    sa.Column('qty', sa.Float(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['product_size_id'], ['product_sizes.id'], name=op.f('fk_product_size_recipe_items_product_size_id_product_sizes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['stock_item_id'], ['stock_items.id'], name=op.f('fk_product_size_recipe_items_stock_item_id_stock_items')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product_size_recipe_items'))
    )
    with op.batch_alter_table('product_size_recipe_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_product_size_recipe_items_product_size_id'), ['product_size_id'], unique=False)

    # Plain ADD COLUMNs (no table rebuild): existing rows are untouched.
    op.add_column('products', sa.Column('long_description', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('tags', sa.JSON(), nullable=True))
    op.add_column('products', sa.Column('featured', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('sale_items', sa.Column('size_id', sa.Integer(), nullable=True))
    op.add_column('sale_items', sa.Column('size_name', sa.String(length=60), nullable=True))
    op.add_column('price_history', sa.Column('size_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('price_history', schema=None) as batch_op:
        batch_op.drop_column('size_id')
    with op.batch_alter_table('sale_items', schema=None) as batch_op:
        batch_op.drop_column('size_name')
        batch_op.drop_column('size_id')
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('featured')
        batch_op.drop_column('tags')
        batch_op.drop_column('long_description')
    with op.batch_alter_table('product_size_recipe_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_product_size_recipe_items_product_size_id'))
    op.drop_table('product_size_recipe_items')
    with op.batch_alter_table('product_sizes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_product_sizes_product_id'))
    op.drop_table('product_sizes')
    op.drop_table('sizes')
