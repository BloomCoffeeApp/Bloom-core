"""sales.table_code

Revision ID: 0035_sale_table_code
Revises: 0034_tables_send_permission
Create Date: 2026-11-16 11:00:00

Additive: the table's own code (PB-SALON-01) is kept on the sale as it was when it was charged (the code of a
table changes if it moves to another zone). Sales that charged a table before this keep today's code of that table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0035_sale_table_code'
down_revision: Union[str, Sequence[str], None] = '0034_tables_send_permission'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('table_code', sa.String(length=24), nullable=True))
    op.execute(
        "UPDATE sales SET table_code = (SELECT code FROM dining_tables WHERE dining_tables.id = sales.table_id) "
        "WHERE table_id IS NOT NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_column('table_code')
