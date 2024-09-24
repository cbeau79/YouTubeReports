"""Add ChannelReport and UserReportAccess models

Revision ID: 348a873f92b8
Revises: b1268ba32163
Create Date: 2024-09-18 16:27:09.179268

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '348a873f92b8'
down_revision = 'b1268ba32163'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('report')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('report',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('channel_id', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('channel_title', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('report_data', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('date_created', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.Column('raw_channel_data', sa.TEXT(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='report_user_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='report_pkey')
    )
    # ### end Alembic commands ###
