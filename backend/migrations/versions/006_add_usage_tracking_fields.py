"""Add text generation and tokens tracking to daily_usage

Revision ID: 006_usage_tracking
Revises: 005_referral_settings
Create Date: 2025-12-30

New columns in daily_usage:
- text_generation_count: Number of text generation API calls
- total_tokens: Total tokens consumed
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '006_usage_tracking'
down_revision = '005_referral_settings'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if column exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Apply migration - adds new usage tracking columns"""

    # Add text_generation_count column
    if not _column_exists('daily_usage', 'text_generation_count'):
        op.add_column('daily_usage',
            sa.Column('text_generation_count', sa.Integer, nullable=False, server_default='0'))

    # Add total_tokens column
    if not _column_exists('daily_usage', 'total_tokens'):
        op.add_column('daily_usage',
            sa.Column('total_tokens', sa.Integer, nullable=False, server_default='0'))


def downgrade() -> None:
    """Rollback migration"""
    if _column_exists('daily_usage', 'total_tokens'):
        op.drop_column('daily_usage', 'total_tokens')
    if _column_exists('daily_usage', 'text_generation_count'):
        op.drop_column('daily_usage', 'text_generation_count')
