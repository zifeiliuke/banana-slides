"""Add referral settings - enabled flag and invitee reward days

Revision ID: 005_referral_settings
Revises: 004_multi_user
Create Date: 2025-12-30

New columns in system_settings:
- referral_enabled: Whether referral system is enabled
- referral_invitee_reward_days: Days awarded to invitee on registration
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '005_referral_settings'
down_revision = '004_multi_user'
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
    """Apply migration - adds new referral settings columns"""

    # Add referral_enabled column
    if not _column_exists('system_settings', 'referral_enabled'):
        op.add_column('system_settings',
            sa.Column('referral_enabled', sa.Boolean, nullable=False, server_default='1'))

    # Add referral_invitee_reward_days column
    if not _column_exists('system_settings', 'referral_invitee_reward_days'):
        op.add_column('system_settings',
            sa.Column('referral_invitee_reward_days', sa.Integer, nullable=False, server_default='1'))


def downgrade() -> None:
    """Rollback migration"""
    if _column_exists('system_settings', 'referral_invitee_reward_days'):
        op.drop_column('system_settings', 'referral_invitee_reward_days')
    if _column_exists('system_settings', 'referral_enabled'):
        op.drop_column('system_settings', 'referral_enabled')
