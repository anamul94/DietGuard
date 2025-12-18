"""make_expires_at_nullable

Revision ID: aff3572e44f2
Revises: 9dac3c5f5fe0
Create Date: 2025-12-18 15:43:40.863616

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aff3572e44f2'
down_revision = '9dac3c5f5fe0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make expires_at nullable for both tables
    op.alter_column('report_data', 'expires_at',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=True)
    op.alter_column('nutrition_data', 'expires_at',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=True)


def downgrade() -> None:
    # Revert expires_at to not nullable
    op.alter_column('nutrition_data', 'expires_at',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)
    op.alter_column('report_data', 'expires_at',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)