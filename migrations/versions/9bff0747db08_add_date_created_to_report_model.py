"""Add date_created to Report model

Revision ID: fc0d4f606892
Revises: previous_revision_id
Create Date: 2024-09-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'fc0d4f606892'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add the column allowing NULL values initially
    op.add_column('report', sa.Column('date_created', sa.DateTime(), nullable=True))
    
    # Update existing rows with the current timestamp
    op.execute("UPDATE report SET date_created = NOW() WHERE date_created IS NULL")
    
    # Alter the column to set it as NOT NULL
    op.alter_column('report', 'date_created', nullable=False)


def downgrade():
    op.drop_column('report', 'date_created')