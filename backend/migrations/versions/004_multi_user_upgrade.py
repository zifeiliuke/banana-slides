"""Multi-user upgrade migration - adds referral, usage tracking, and email verification

Revision ID: 004_multi_user
Revises: 38292967f3ca
Create Date: 2025-12-26

Tables created:
- system_settings: Global system configuration
- referrals: Invitation/referral records
- daily_usage: Daily API usage tracking
- email_verifications: Email verification codes

User table changes:
- referral_code: User's unique referral code
- referred_by_user_id: ID of user who referred this user
- email_verified: Whether email is verified
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from datetime import datetime
import uuid


# revision identifiers, used by Alembic.
revision = '004_multi_user'
down_revision = '38292967f3ca'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    """Check if table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if column exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Apply migration - creates new tables and adds columns to users table"""

    # ========== Create system_settings table ==========
    if not _table_exists('system_settings'):
        op.create_table('system_settings',
            sa.Column('id', sa.String(36), primary_key=True),
            # Registration settings
            sa.Column('default_user_tier', sa.String(20), nullable=False, server_default='free'),
            sa.Column('default_premium_days', sa.Integer, nullable=False, server_default='30'),
            sa.Column('require_email_verification', sa.Boolean, nullable=False, server_default='0'),
            # Referral settings
            sa.Column('referral_register_reward_days', sa.Integer, nullable=False, server_default='1'),
            sa.Column('referral_premium_reward_days', sa.Integer, nullable=False, server_default='3'),
            sa.Column('referral_domain', sa.String(200), nullable=False, server_default='ppt.netopstec.com'),
            # Usage limits
            sa.Column('daily_image_generation_limit', sa.Integer, nullable=False, server_default='20'),
            sa.Column('enable_usage_limit', sa.Boolean, nullable=False, server_default='1'),
            # SMTP settings
            sa.Column('smtp_host', sa.String(200), nullable=True),
            sa.Column('smtp_port', sa.Integer, nullable=True, server_default='465'),
            sa.Column('smtp_user', sa.String(200), nullable=True),
            sa.Column('smtp_password', sa.String(500), nullable=True),
            sa.Column('smtp_use_ssl', sa.Boolean, nullable=False, server_default='1'),
            sa.Column('smtp_sender_name', sa.String(100), nullable=True, server_default='Banana Slides'),
            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        )
        # Insert default settings row
        op.execute(f"INSERT INTO system_settings (id) VALUES ('{str(uuid.uuid4())}')")

    # ========== Create referrals table ==========
    if not _table_exists('referrals'):
        op.create_table('referrals',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('inviter_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
            sa.Column('invitee_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True, index=True),
            sa.Column('invitee_email', sa.String(100), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
            # Reward status
            sa.Column('register_reward_granted', sa.Boolean, nullable=False, server_default='0'),
            sa.Column('register_reward_days', sa.Integer, nullable=True),
            sa.Column('register_reward_at', sa.DateTime, nullable=True),
            sa.Column('premium_reward_granted', sa.Boolean, nullable=False, server_default='0'),
            sa.Column('premium_reward_days', sa.Integer, nullable=True),
            sa.Column('premium_reward_at', sa.DateTime, nullable=True),
            # Timestamps
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        )

    # ========== Create daily_usage table ==========
    if not _table_exists('daily_usage'):
        op.create_table('daily_usage',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
            sa.Column('usage_date', sa.Date, nullable=False, index=True),
            sa.Column('image_generation_count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('used_system_api', sa.Boolean, nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('user_id', 'usage_date', name='uq_user_date'),
        )

    # ========== Create email_verifications table ==========
    if not _table_exists('email_verifications'):
        op.create_table('email_verifications',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('email', sa.String(100), nullable=False, index=True),
            sa.Column('code', sa.String(6), nullable=False),
            sa.Column('expires_at', sa.DateTime, nullable=False),
            sa.Column('is_used', sa.Boolean, nullable=False, server_default='0'),
            sa.Column('used_at', sa.DateTime, nullable=True),
            sa.Column('attempts', sa.Integer, nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )

    # ========== Add new columns to users table ==========
    if not _column_exists('users', 'referral_code'):
        op.add_column('users', sa.Column('referral_code', sa.String(16), nullable=True, unique=True))
        op.create_index('ix_users_referral_code', 'users', ['referral_code'])

    if not _column_exists('users', 'referred_by_user_id'):
        op.add_column('users', sa.Column('referred_by_user_id', sa.String(36), nullable=True))

    if not _column_exists('users', 'email_verified'):
        op.add_column('users', sa.Column('email_verified', sa.Boolean, nullable=False, server_default='0'))


def downgrade() -> None:
    """Rollback migration"""
    # Drop columns from users table
    if _column_exists('users', 'email_verified'):
        op.drop_column('users', 'email_verified')
    if _column_exists('users', 'referred_by_user_id'):
        op.drop_column('users', 'referred_by_user_id')
    if _column_exists('users', 'referral_code'):
        op.drop_index('ix_users_referral_code', 'users')
        op.drop_column('users', 'referral_code')

    # Drop new tables
    if _table_exists('email_verifications'):
        op.drop_table('email_verifications')
    if _table_exists('daily_usage'):
        op.drop_table('daily_usage')
    if _table_exists('referrals'):
        op.drop_table('referrals')
    if _table_exists('system_settings'):
        op.drop_table('system_settings')
