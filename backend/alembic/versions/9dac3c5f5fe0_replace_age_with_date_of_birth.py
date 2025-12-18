"""replace_age_with_date_of_birth

Revision ID: 9dac3c5f5fe0
Revises: 7cb87dd40631
Create Date: 2025-12-18 15:17:28.582913

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9dac3c5f5fe0'
down_revision = '7cb87dd40631'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add date_of_birth column
    op.add_column('users', sa.Column('date_of_birth', sa.DateTime(timezone=True), nullable=True))
    
    # Drop age column
    op.drop_column('users', 'age')


def downgrade() -> None:
    # Add age column back
    op.add_column('users', sa.Column('age', sa.Integer(), nullable=True))
    
    # Drop date_of_birth column
    op.drop_column('users', 'date_of_birth')