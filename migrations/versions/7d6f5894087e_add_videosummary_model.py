"""Add VideoSummary model

Revision ID: 7d6f5894087e
Revises: ba9a14ee8ff4
Create Date: 2024-09-23 10:39:38.639232

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d6f5894087e'
down_revision = 'ba9a14ee8ff4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('video_summary',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('video_id', sa.String(length=100), nullable=False),
    sa.Column('video_title', sa.String(length=200), nullable=False),
    sa.Column('summary_data', sa.Text(), nullable=False),
    sa.Column('raw_video_data', sa.Text(), nullable=True),
    sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('video_id')
    )
    with op.batch_alter_table('user_report_access', schema=None) as batch_op:
        batch_op.drop_index('ix_user_report_access_report_id')
        batch_op.drop_index('ix_user_report_access_user_id')
        batch_op.drop_constraint('user_report_access_temp_user_id_report_id_key', type_='unique')
        batch_op.create_unique_constraint('uq_user_report', ['user_id', 'report_id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_report_access', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_report', type_='unique')
        batch_op.create_unique_constraint('user_report_access_temp_user_id_report_id_key', ['user_id', 'report_id'])
        batch_op.create_index('ix_user_report_access_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_user_report_access_report_id', ['report_id'], unique=False)

    op.drop_table('video_summary')
    # ### end Alembic commands ###
