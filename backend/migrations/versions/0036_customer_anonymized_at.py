"""customers.anonymized_at

Revision ID: 0036_customer_anonymized_at
Revises: 0035_sale_table_code
Create Date: 2026-11-17 16:00:00

Additive: marks a customer card that was anonymized at the person's request (Ley 25.326, right of suppression).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0036_customer_anonymized_at'
down_revision: Union[str, Sequence[str], None] = '0035_sale_table_code'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('anonymized_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_column('anonymized_at')
