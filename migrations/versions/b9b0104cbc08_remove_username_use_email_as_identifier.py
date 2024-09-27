"""Remove username, use email as identifier

Revision ID: b9b0104cbc08
Revises: 971de0dc239c
Create Date: 2024-09-26 16:02:30.101546

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b9b0104cbc08'
down_revision = '971de0dc239c'
branch_labels = None
depends_on = None

def upgrade():
    # Create a unique constraint on email if it doesn't exist
    op.create_unique_constraint('uq_user_email', 'user', ['email'])
    
    # Drop the username column
    op.drop_column('user', 'username')

def downgrade():
    # Add the username column back
    op.add_column('user', sa.Column('username', sa.String(length=100), nullable=True))
    
    # Copy data from email to username
    op.execute("UPDATE \"user\" SET username = email")
    
    # Make username non-nullable and unique
    op.alter_column('user', 'username', nullable=False)
    op.create_unique_constraint('uq_user_username', 'user', ['username'])
    
    # Remove the unique constraint on email
    op.drop_constraint('uq_user_email', 'user', type_='unique')