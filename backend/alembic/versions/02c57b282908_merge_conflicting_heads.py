"""merge_conflicting_heads

Revision ID: 02c57b282908
Revises: bab38266222b, c4f7d9a2b1e3
Create Date: 2026-03-13 15:51:06.822164

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '02c57b282908'
down_revision = ('bab38266222b', 'c4f7d9a2b1e3')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass