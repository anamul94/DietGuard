"""add_packages_table_and_link_subscriptions

Revision ID: 7cb87dd40631
Revises: a0e7dd2be033
Create Date: 2025-12-16 16:41:09.484238

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7cb87dd40631'
down_revision = 'a0e7dd2be033'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create packages table
    op.create_table('packages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('billing_period', sa.String(length=20), nullable=False),
        sa.Column('daily_upload_limit', sa.Integer(), nullable=False),
        sa.Column('daily_nutrition_limit', sa.Integer(), nullable=False),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_packages_id'), 'packages', ['id'], unique=False)
    op.create_index(op.f('ix_packages_name'), 'packages', ['name'], unique=True)
    
    # Add package_id column as nullable first
    op.add_column('subscriptions', sa.Column('package_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_subscriptions_package_id'), 'subscriptions', ['package_id'], unique=False)
    op.create_foreign_key('fk_subscriptions_package_id', 'subscriptions', 'packages', ['package_id'], ['id'])
    
    # Note: Existing subscriptions will have NULL package_id
    # They should be updated by application logic or manual SQL to assign a default package
    # ### end Alembic commands ###


def downgrade() -> None:
    # Drop foreign key and column from subscriptions
    op.drop_constraint('fk_subscriptions_package_id', 'subscriptions', type_='foreignkey')
    op.drop_index(op.f('ix_subscriptions_package_id'), table_name='subscriptions')
    op.drop_column('subscriptions', 'package_id')
    
    # Drop packages table
    op.drop_index(op.f('ix_packages_name'), table_name='packages')
    op.drop_index(op.f('ix_packages_id'), table_name='packages')
    op.drop_table('packages')
    # ### end Alembic commands ###