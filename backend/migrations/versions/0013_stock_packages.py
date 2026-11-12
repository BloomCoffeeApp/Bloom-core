"""stock packages: package types per stock item ("6 leches de 1 L", "caja de 6 × 250 ml")

Revision ID: 0013_stock_packages
Revises: 0012_expenses
Create Date: 2026-11-06 15:00:00

Purely additive. Stock keeps its base unit (g/ml/u); a package is `content_qty` base units with an
optional barcode and last cost per package. Nothing changes for items without packages.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0013_stock_packages'
down_revision: Union[str, Sequence[str], None] = '0012_expenses'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('stock_packages',
    sa.Column('stock_item_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('content_qty', sa.Float(), nullable=False),
    sa.Column('barcode', sa.String(length=40), nullable=True),
    sa.Column('cost_cents', sa.Integer(), nullable=True),
    sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['stock_item_id'], ['stock_items.id'], name=op.f('fk_stock_packages_stock_item_id_stock_items'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_packages')),
    )
    op.create_index(op.f('ix_stock_packages_stock_item_id'), 'stock_packages', ['stock_item_id'], unique=False)
    op.create_index(op.f('ix_stock_packages_barcode'), 'stock_packages', ['barcode'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_stock_packages_barcode'), table_name='stock_packages')
    op.drop_index(op.f('ix_stock_packages_stock_item_id'), table_name='stock_packages')
    op.drop_table('stock_packages')
