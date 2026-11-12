"""table sessions

Revision ID: 0017_table_sessions
Revises: 0016_sale_delivery_fee
Create Date: 2026-11-12 19:30:00

Purely additive: `table_diners` (one row per phone at a table's open account; only the token's hash),
`table_tabs.join_code` / `last_activity_at` and `orders.diner_id`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0017_table_sessions'
down_revision: Union[str, Sequence[str], None] = '0016_sale_delivery_fee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('table_tabs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('join_code', sa.String(length=4), nullable=True))
        batch_op.add_column(sa.Column('last_activity_at', sa.DateTime(), nullable=True))
    op.create_table('table_diners',
    sa.Column('tab_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('approved', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('trusted', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('blocked', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('client_ip', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['tab_id'], ['table_tabs.id'], name=op.f('fk_table_diners_tab_id_table_tabs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_table_diners')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_table_diners_token_hash'))
    )
    with op.batch_alter_table('table_diners', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_table_diners_tab_id'), ['tab_id'], unique=False)
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('diner_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_orders_diner_id'), ['diner_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_orders_diner_id_table_diners'), 'table_diners', ['diner_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_orders_diner_id_table_diners'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_orders_diner_id'))
        batch_op.drop_column('diner_id')
    op.drop_table('table_diners')
    with op.batch_alter_table('table_tabs', schema=None) as batch_op:
        batch_op.drop_column('last_activity_at')
        batch_op.drop_column('join_code')
