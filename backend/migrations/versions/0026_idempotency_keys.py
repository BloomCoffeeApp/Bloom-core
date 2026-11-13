"""idempotency keys for money-moving requests

Revision ID: 0026_idempotency_keys
Revises: 0025_user_permission_overrides
Create Date: 2026-11-13 20:00:00

Purely additive: one table. A request that carries `Idempotency-Key` (sales, cash movements, account payments)
is recorded here with the id of what it created; sending the same key again returns that instead of repeating it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0026_idempotency_keys'
down_revision: Union[str, Sequence[str], None] = '0025_user_permission_overrides'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'idempotency_keys',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('scope', sa.String(length=30), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('body_hash', sa.String(length=64), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )
    op.create_index(op.f('ix_idempotency_keys_created_at'), 'idempotency_keys', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_idempotency_keys_created_at'), table_name='idempotency_keys')
    op.drop_table('idempotency_keys')
