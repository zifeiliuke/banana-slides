"""merge all migration heads after refactoring

Revision ID: 008_merge_all_heads
Revises: 006_add_export_settings, 006_usage_tracking
Create Date: 2026-01-05

This merge migration combines two parallel branches:
- Branch A (main): 004_template_style -> 005_pdf_image_path -> 006_export_settings
- Branch B (multi-user): 007_merge_heads -> 005_referral -> 006_usage_tracking

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_merge_all_heads'
down_revision = ('006_add_export_settings', '006_usage_tracking')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration, no schema changes needed
    pass


def downgrade():
    # This is a merge migration, no schema changes needed
    pass
