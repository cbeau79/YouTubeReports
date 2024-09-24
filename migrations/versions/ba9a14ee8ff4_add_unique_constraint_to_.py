"""Add unique constraint to UserReportAccess

Revision ID: ba9a14ee8ff4
Revises: 6d7f534270ed
Create Date: 2024-09-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ba9a14ee8ff4'
down_revision = '6d7f534270ed'
branch_labels = None
depends_on = None

def upgrade():
    # Create a temporary table with the structure we want
    op.execute("""
    CREATE TABLE user_report_access_temp (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        report_id INTEGER NOT NULL,
        date_accessed TIMESTAMP WITH TIME ZONE NOT NULL,
        UNIQUE (user_id, report_id)
    )
    """)

    # Copy data from the original table to the temporary table, 
    # keeping only the most recent access for each user-report pair
    op.execute("""
    INSERT INTO user_report_access_temp (user_id, report_id, date_accessed)
    SELECT DISTINCT ON (user_id, report_id) user_id, report_id, MAX(date_accessed) as date_accessed
    FROM user_report_access
    GROUP BY user_id, report_id
    """)

    # Drop the original table
    op.drop_table('user_report_access')

    # Rename the temporary table to the original name
    op.rename_table('user_report_access_temp', 'user_report_access')

    # Add back any indexes or foreign keys that were on the original table
    # (You may need to adjust this based on your specific schema)
    op.create_index(op.f('ix_user_report_access_report_id'), 'user_report_access', ['report_id'], unique=False)
    op.create_index(op.f('ix_user_report_access_user_id'), 'user_report_access', ['user_id'], unique=False)
    op.create_foreign_key(None, 'user_report_access', 'user', ['user_id'], ['id'])
    op.create_foreign_key(None, 'user_report_access', 'channel_report', ['report_id'], ['id'])

def downgrade():
    # Remove the unique constraint
    op.drop_constraint('uq_user_report', 'user_report_access', type_='unique')