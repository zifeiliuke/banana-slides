"""merge multi_user and template_style heads

Revision ID: 007_merge_heads
Revises: 004_add_template_style, 004_multi_user
Create Date: 2024-12-30 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_merge_heads'
down_revision = ('004_add_template_style', '004_multi_user')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration, no schema changes needed
    pass


def downgrade():
    # This is a merge migration, no schema changes needed
    pass
