"""
Points models - 积分体系相关模型
"""
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, case, or_
from . import db


class PointsBalance(db.Model):
    """
    积分批次表 - 记录每一批积分的来源和有效期
    支持FIFO消耗策略（先过期先消耗）
    """
    __tablename__ = 'points_balance'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # 积分信息
    amount = db.Column(db.Integer, nullable=False)  # 原始积分数量
    remaining = db.Column(db.Integer, nullable=False)  # 剩余积分数量（可为负数）

    # 来源信息
    source = db.Column(db.String(32), nullable=False)  # 来源类型
    source_id = db.Column(db.String(36), nullable=True)  # 关联ID（如充值码ID）
    source_note = db.Column(db.Text, nullable=True)  # 备注说明

    # 有效期
    expires_at = db.Column(db.DateTime, nullable=True)  # 过期时间，NULL表示永不过期

    # 时间戳
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        db.Index('idx_points_balance_user_expires', 'user_id', 'expires_at'),
        db.Index('idx_points_balance_source', 'source', 'source_id'),
    )

    # Relationships
    user = db.relationship('User', backref=db.backref('points_balances', lazy='dynamic'))

    # Source 枚举值
    SOURCE_REGISTER = 'register'  # 注册赠送
    SOURCE_RECHARGE = 'recharge'  # 充值码兑换
    SOURCE_REFERRAL_INVITER_REGISTER = 'referral_inviter_register'  # 邀请者注册奖励
    SOURCE_REFERRAL_INVITEE_REGISTER = 'referral_invitee_register'  # 被邀请者注册奖励
    SOURCE_REFERRAL_INVITER_UPGRADE = 'referral_inviter_upgrade'  # 邀请者升级奖励
    SOURCE_ADMIN_GRANT = 'admin_grant'  # 管理员手动发放
    SOURCE_ADMIN_DEDUCT = 'admin_deduct'  # 管理员手动扣除
    SOURCE_MIGRATION = 'migration'  # 历史数据迁移

    def is_expired(self) -> bool:
        """检查此批次是否已过期"""
        if self.expires_at is None:
            return False
        now = datetime.now(timezone.utc)
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= now

    def is_valid(self) -> bool:
        """检查此批次是否有效（未过期且有剩余）"""
        return not self.is_expired() and self.remaining > 0

    def get_valid_remaining(self) -> int:
        """获取有效剩余积分（过期则返回0）"""
        if self.is_expired():
            return 0
        return max(0, self.remaining)

    def to_dict(self):
        """转换为字典"""
        now = datetime.now(timezone.utc)
        is_expiring_soon = False
        if self.expires_at:
            expires_at = self.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            # 7天内过期视为即将过期
            is_expiring_soon = expires_at > now and expires_at <= now + timedelta(days=7)

        return {
            'id': self.id,
            'amount': self.amount,
            'remaining': self.remaining,
            'valid_remaining': self.get_valid_remaining(),
            'source': self.source,
            'source_id': self.source_id,
            'source_note': self.source_note,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired(),
            'is_expiring_soon': is_expiring_soon,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def get_source_display(cls, source: str) -> str:
        """获取来源的显示文本"""
        display_map = {
            cls.SOURCE_REGISTER: '注册赠送',
            cls.SOURCE_RECHARGE: '充值码兑换',
            cls.SOURCE_REFERRAL_INVITER_REGISTER: '邀请注册奖励',
            cls.SOURCE_REFERRAL_INVITEE_REGISTER: '受邀注册奖励',
            cls.SOURCE_REFERRAL_INVITER_UPGRADE: '邀请升级奖励',
            cls.SOURCE_ADMIN_GRANT: '管理员发放',
            cls.SOURCE_ADMIN_DEDUCT: '管理员扣除',
            cls.SOURCE_MIGRATION: '历史迁移',
        }
        return display_map.get(source, source)

    def __repr__(self):
        return f'<PointsBalance user={self.user_id} amount={self.amount} remaining={self.remaining}>'


class PointsTransaction(db.Model):
    """
    积分流水表 - 记录所有积分变动明细
    """
    __tablename__ = 'points_transaction'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # 变动信息
    type = db.Column(db.String(16), nullable=False)  # income/expense/expired
    amount = db.Column(db.Integer, nullable=False)  # 变动数量（正数）
    balance_after = db.Column(db.Integer, nullable=False)  # 变动后总有效余额

    # 关联信息
    balance_id = db.Column(db.String(36), db.ForeignKey('points_balance.id', ondelete='SET NULL'), nullable=True)
    description = db.Column(db.String(255), nullable=True)  # 描述

    # 时间戳
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        db.Index('idx_points_transaction_user_created', 'user_id', 'created_at'),
    )

    # Relationships
    user = db.relationship('User', backref=db.backref('points_transactions', lazy='dynamic'))
    balance = db.relationship('PointsBalance', backref=db.backref('transactions', lazy='dynamic'))

    # Type 枚举值
    TYPE_INCOME = 'income'  # 积分收入
    TYPE_EXPENSE = 'expense'  # 积分消耗
    TYPE_EXPIRED = 'expired'  # 积分过期

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'amount': self.amount,
            'balance_after': self.balance_after,
            'balance_id': self.balance_id,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def get_type_display(cls, type_: str) -> str:
        """获取类型的显示文本"""
        display_map = {
            cls.TYPE_INCOME: '收入',
            cls.TYPE_EXPENSE: '支出',
            cls.TYPE_EXPIRED: '过期',
        }
        return display_map.get(type_, type_)

    def __repr__(self):
        return f'<PointsTransaction user={self.user_id} type={self.type} amount={self.amount}>'
