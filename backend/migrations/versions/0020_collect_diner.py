"""collect charges: the table diner who paid

Revision ID: 0020_collect_diner
Revises: 0019_order_invoice_request
Create Date: 2026-11-12 22:00:00

Purely additive: `collect_charges.diner_id` (Pro «Pagar desde la mesa»: which phone paid).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0020_collect_diner'
down_revision: Union[str, Sequence[str], None] = '0019_order_invoice_request'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('collect_charges', schema=None) as batch_op:
        batch_op.add_column(sa.Column('diner_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_collect_charges_diner_id'), ['diner_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_collect_charges_diner_id_table_diners'), 'table_diners', ['diner_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('collect_charges', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_collect_charges_diner_id_table_diners'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_collect_charges_diner_id'))
        batch_op.drop_column('diner_id')
