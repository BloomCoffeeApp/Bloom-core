"""sale courtesy: sales given away on the house (stock moves, no money)

Revision ID: 0003_sale_courtesy
Revises: 0002_drink_guides
Create Date: 2026-10-31 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_sale_courtesy'
down_revision: Union[str, Sequence[str], None] = '0002_drink_guides'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_courtesy', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('courtesy_cents', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('courtesy_reason', sa.String(length=200), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_column('courtesy_reason')
        batch_op.drop_column('courtesy_cents')
        batch_op.drop_column('is_courtesy')
