"""Create initial tables

Revision ID: bab38266222b
Revises: 47b08e5adfbc
Create Date: 2025-12-26 17:32:53.876048

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'bab38266222b'
down_revision = '47b08e5adfbc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add meal tracking columns to nutrition_data
    op.add_column('nutrition_data', sa.Column('meal_time', sa.Time(), nullable=True))
    op.add_column('nutrition_data', sa.Column('meal_date', sa.Date(), nullable=True))
    
    # Add indexes for efficient querying
    op.create_index('idx_nutrition_data_user_date', 'nutrition_data', ['user_id', 'meal_date'], unique=False)


def downgrade() -> None:
    # Remove meal tracking columns and indexes
    op.drop_index('idx_nutrition_data_user_date', table_name='nutrition_data')
    op.drop_column('nutrition_data', 'meal_date')
    op.drop_column('nutrition_data', 'meal_time')