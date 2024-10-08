"""Add categorization fields to ChannelReport

Revision ID: 9109b4997e0b
Revises: e38918002000
Create Date: 2024-09-25 14:45:34.882945

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9109b4997e0b'
down_revision = 'e38918002000'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('channel_report', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_categories', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('video_formats', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('content_category_justification', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('content_category_confidence', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('channel_report', schema=None) as batch_op:
        batch_op.drop_column('content_category_confidence')
        batch_op.drop_column('content_category_justification')
        batch_op.drop_column('video_formats')
        batch_op.drop_column('content_categories')

    # ### end Alembic commands ###
