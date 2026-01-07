"""Add points system for new membership model

Revision ID: 009_points_system
Revises: 008_merge_all_heads
Create Date: 2026-01-07

This migration introduces a points-based membership system:
- Creates points_balance table for tracking point batches with expiration
- Creates points_transaction table for transaction history
- Modifies recharge_codes table to support points instead of days
- Modifies system_settings table for points configuration
- Migrates existing user data to the new points system
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from datetime import datetime, timedelta
import uuid


# revision identifiers, used by Alembic.
revision = '009_points_system'
down_revision = '008_merge_all_heads'
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
    """Apply migration - adds points system"""
    bind = op.get_bind()

    # ========== 1. Create points_balance table ==========
    if not _table_exists('points_balance'):
        op.create_table(
            'points_balance',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('amount', sa.Integer, nullable=False),
            sa.Column('remaining', sa.Integer, nullable=False),
            sa.Column('source', sa.String(32), nullable=False),
            sa.Column('source_id', sa.String(36), nullable=True),
            sa.Column('source_note', sa.Text, nullable=True),
            sa.Column('expires_at', sa.DateTime, nullable=True),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index('idx_points_balance_user_expires', 'points_balance', ['user_id', 'expires_at'])
        op.create_index('idx_points_balance_source', 'points_balance', ['source', 'source_id'])

    # ========== 2. Create points_transaction table ==========
    if not _table_exists('points_transaction'):
        op.create_table(
            'points_transaction',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('type', sa.String(16), nullable=False),
            sa.Column('amount', sa.Integer, nullable=False),
            sa.Column('balance_after', sa.Integer, nullable=False),
            sa.Column('balance_id', sa.String(36), sa.ForeignKey('points_balance.id', ondelete='SET NULL'), nullable=True),
            sa.Column('description', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index('idx_points_transaction_user_created', 'points_transaction', ['user_id', 'created_at'])

    # ========== 3. Modify recharge_codes table ==========
    if not _column_exists('recharge_codes', 'points'):
        op.add_column('recharge_codes',
            sa.Column('points', sa.Integer, nullable=False, server_default='0'))

    if not _column_exists('recharge_codes', 'points_expire_days'):
        op.add_column('recharge_codes',
            sa.Column('points_expire_days', sa.Integer, nullable=True))

    # Make duration_days nullable (deprecated)
    if _column_exists('recharge_codes', 'duration_days'):
        op.alter_column('recharge_codes', 'duration_days',
            existing_type=sa.Integer,
            nullable=True)

    # ========== 4. Modify system_settings table ==========
    # Points configuration
    if not _column_exists('system_settings', 'points_per_page'):
        op.add_column('system_settings',
            sa.Column('points_per_page', sa.Integer, nullable=False, server_default='15'))

    if not _column_exists('system_settings', 'register_bonus_points'):
        op.add_column('system_settings',
            sa.Column('register_bonus_points', sa.Integer, nullable=False, server_default='300'))

    if not _column_exists('system_settings', 'register_bonus_expire_days'):
        op.add_column('system_settings',
            sa.Column('register_bonus_expire_days', sa.Integer, nullable=True, server_default='3'))

    # Referral points configuration
    if not _column_exists('system_settings', 'referral_inviter_register_points'):
        op.add_column('system_settings',
            sa.Column('referral_inviter_register_points', sa.Integer, nullable=False, server_default='100'))

    if not _column_exists('system_settings', 'referral_invitee_register_points'):
        op.add_column('system_settings',
            sa.Column('referral_invitee_register_points', sa.Integer, nullable=False, server_default='100'))

    if not _column_exists('system_settings', 'referral_inviter_upgrade_points'):
        op.add_column('system_settings',
            sa.Column('referral_inviter_upgrade_points', sa.Integer, nullable=False, server_default='450'))

    if not _column_exists('system_settings', 'referral_points_expire_days'):
        op.add_column('system_settings',
            sa.Column('referral_points_expire_days', sa.Integer, nullable=True))

    # Make deprecated columns nullable
    deprecated_columns = [
        ('system_settings', 'default_user_tier'),
        ('system_settings', 'default_premium_days'),
        ('system_settings', 'referral_register_reward_days'),
        ('system_settings', 'referral_invitee_reward_days'),
        ('system_settings', 'referral_premium_reward_days'),
        ('system_settings', 'daily_image_generation_limit'),
        ('system_settings', 'enable_usage_limit'),
        ('users', 'tier'),
    ]
    for table, col in deprecated_columns:
        if _column_exists(table, col):
            try:
                op.alter_column(table, col, existing_type=sa.String(20) if col in ['default_user_tier', 'tier'] else sa.Integer, nullable=True)
            except Exception:
                pass  # Ignore if column type mismatch or already nullable

    # ========== 5. Data Migration ==========
    # Migrate existing premium users: grant points based on their usage history

    # 5.1 Users who have used recharge codes: grant 6000 points (30 days) + 300 permanent
    result = bind.execute(text("""
        SELECT DISTINCT u.id
        FROM users u
        WHERE EXISTS (
            SELECT 1 FROM recharge_codes rc
            WHERE rc.used_by_user_id = u.id AND rc.is_used = TRUE
        )
    """))
    users_with_codes = [row[0] for row in result]

    now = datetime.utcnow()
    for user_id in users_with_codes:
        # Grant 6000 points with 30-day expiration
        balance_id_1 = str(uuid.uuid4())
        bind.execute(text("""
            INSERT INTO points_balance (id, user_id, amount, remaining, source, source_note, expires_at, created_at)
            VALUES (:id, :user_id, 6000, 6000, 'migration', '历史会员迁移奖励（30天有效）', :expires_at, :created_at)
        """), {
            'id': balance_id_1,
            'user_id': user_id,
            'expires_at': now + timedelta(days=30),
            'created_at': now
        })

        # Grant 300 permanent points
        balance_id_2 = str(uuid.uuid4())
        bind.execute(text("""
            INSERT INTO points_balance (id, user_id, amount, remaining, source, source_note, expires_at, created_at)
            VALUES (:id, :user_id, 300, 300, 'migration', '历史会员永久奖励', NULL, :created_at)
        """), {
            'id': balance_id_2,
            'user_id': user_id,
            'created_at': now
        })

        # Record transaction
        trans_id = str(uuid.uuid4())
        bind.execute(text("""
            INSERT INTO points_transaction (id, user_id, type, amount, balance_after, balance_id, description, created_at)
            VALUES (:id, :user_id, 'income', 6300, 6300, :balance_id, '历史数据迁移积分', :created_at)
        """), {
            'id': trans_id,
            'user_id': user_id,
            'balance_id': balance_id_1,
            'created_at': now
        })

    # 5.2 Update unused recharge codes: set points = 300, points_expire_days = NULL
    bind.execute(text("""
        UPDATE recharge_codes
        SET points = 300, points_expire_days = NULL
        WHERE is_used = FALSE AND points = 0
    """))


def downgrade() -> None:
    """Rollback migration"""
    bind = op.get_bind()

    # Remove data first
    if _table_exists('points_transaction'):
        bind.execute(text("DELETE FROM points_transaction"))
    if _table_exists('points_balance'):
        bind.execute(text("DELETE FROM points_balance"))

    # Drop new columns from system_settings
    new_system_columns = [
        'points_per_page',
        'register_bonus_points',
        'register_bonus_expire_days',
        'referral_inviter_register_points',
        'referral_invitee_register_points',
        'referral_inviter_upgrade_points',
        'referral_points_expire_days',
    ]
    for col in new_system_columns:
        if _column_exists('system_settings', col):
            op.drop_column('system_settings', col)

    # Drop new columns from recharge_codes
    if _column_exists('recharge_codes', 'points_expire_days'):
        op.drop_column('recharge_codes', 'points_expire_days')
    if _column_exists('recharge_codes', 'points'):
        op.drop_column('recharge_codes', 'points')

    # Drop tables
    if _table_exists('points_transaction'):
        op.drop_table('points_transaction')
    if _table_exists('points_balance'):
        op.drop_table('points_balance')
