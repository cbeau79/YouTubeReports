"""Add user_id to VideoSummary

Revision ID: e38918002000
Revises: 7d6f5894087e
Create Date: 2023-05-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e38918002000'
down_revision = '7d6f5894087e'
branch_labels = None
depends_on = None

def upgrade():
    # Step 1: Add user_id column as nullable
    op.add_column('video_summary', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Step 2: Create a default user if none exists
    op.execute("""
    INSERT INTO "user" (username, password)
    SELECT 'default_user', 'default_password'
    WHERE NOT EXISTS (SELECT 1 FROM "user" LIMIT 1)
    """)
    
    # Step 3: Update existing records with the default user's id
    op.execute("""
    UPDATE video_summary
    SET user_id = (SELECT id FROM "user" ORDER BY id LIMIT 1)
    WHERE user_id IS NULL
    """)
    
    # Step 4: Add non-nullable constraint
    op.alter_column('video_summary', 'user_id',
               existing_type=sa.Integer(),
               nullable=False)
    
    # Step 5: Add foreign key constraint
    op.create_foreign_key(None, 'video_summary', 'user', ['user_id'], ['id'])

def downgrade():
    # Remove foreign key constraint
    op.drop_constraint(None, 'video_summary', type_='foreignkey')
    
    # Remove user_id column
    op.drop_column('video_summary', 'user_id')