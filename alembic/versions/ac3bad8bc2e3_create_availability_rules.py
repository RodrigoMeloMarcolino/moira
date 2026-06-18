"""create availability rules

Revision ID: ac3bad8bc2e3
Revises: 86049b9c6690
Create Date: 2026-06-12 00:20:04.210794

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ac3bad8bc2e3'
down_revision: str | Sequence[str] | None = '86049b9c6690'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'availability_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider_id', sa.UUID(), nullable=False),
        sa.Column('weekday', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint('start_time < end_time', name='ck_start_before_end'),
        sa.CheckConstraint(
            'weekday >= 1 AND weekday <= 7',
            name='ck_weekday_valid_range',
        ),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'idx_availability_rules_provider_id_weekday',
        'availability_rules',
        ['provider_id', 'weekday'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'idx_availability_rules_provider_id_weekday',
        table_name='availability_rules',
    )
    op.drop_table('availability_rules')
