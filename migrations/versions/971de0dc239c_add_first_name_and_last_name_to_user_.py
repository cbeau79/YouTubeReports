"""Add first_name, last_name, and email to User model

Revision ID: 971de0dc239c
Revises: 7b96794ec948
Create Date: 2024-09-26 15:52:09.709895

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '971de0dc239c'
down_revision = '7b96794ec948'
branch_labels = None
depends_on = None

def upgrade():
    # Add columns as nullable
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('first_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('last_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))

    # Update existing users with their username as email
    op.execute("UPDATE \"user\" SET email = username WHERE email IS NULL")

    # Make email column NOT NULL
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('email', nullable=False)

def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('email')
        batch_op.drop_column('last_name')
        batch_op.drop_column('first_name')