"""collect charges: provider operation id

Revision ID: 0018_collect_operation_id
Revises: 0017_table_sessions
Create Date: 2026-11-12 21:00:00

Purely additive: `collect_charges.operation_id` (the provider's payment number, for receipts).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0018_collect_operation_id'
down_revision: Union[str, Sequence[str], None] = '0017_table_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('collect_charges', schema=None) as batch_op:
        batch_op.add_column(sa.Column('operation_id', sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('collect_charges', schema=None) as batch_op:
        batch_op.drop_column('operation_id')
