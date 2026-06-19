"""add appointment idempotency

Revision ID: d4f6a1b7c9e2
Revises: ac3bad8bc2e3
Create Date: 2026-06-18 14:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4f6a1b7c9e2'
down_revision: str | Sequence[str] | None = 'ac3bad8bc2e3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'appointments',
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'appointments',
        sa.Column('idempotency_fingerprint', sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        'uq_appointments_provider_idempotency_key',
        'appointments',
        ['provider_id', 'idempotency_key'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_appointments_provider_idempotency_key',
        'appointments',
        type_='unique',
    )
    op.drop_column('appointments', 'idempotency_fingerprint')
    op.drop_column('appointments', 'idempotency_key')
