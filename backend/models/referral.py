"""
Referral model - stores invitation/referral records for user growth
"""
import uuid
import secrets
import string
from datetime import datetime, timezone
from . import db


class Referral(db.Model):
    """
    邀请记录模型 - 记录用户邀请关系和奖励发放
    """
    __tablename__ = 'referrals'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 邀请者用户ID
    inviter_user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    # 被邀请者用户ID（注册后填充）
    invitee_user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True, index=True)
    # 被邀请者邮箱（用于追踪未注册的邀请）
    invitee_email = db.Column(db.String(100), nullable=True)

    # 邀请状态: pending(待注册), registered(已注册), premium(已成为会员)
    status = db.Column(db.String(20), nullable=False, default='pending')

    # 奖励发放状态
    register_reward_granted = db.Column(db.Boolean, nullable=False, default=False)
    register_reward_days = db.Column(db.Integer, nullable=True)  # 实际发放的天数
    register_reward_at = db.Column(db.DateTime, nullable=True)

    premium_reward_granted = db.Column(db.Boolean, nullable=False, default=False)
    premium_reward_days = db.Column(db.Integer, nullable=True)  # 实际发放的天数
    premium_reward_at = db.Column(db.DateTime, nullable=True)

    # 时间戳
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    inviter = db.relationship('User', foreign_keys=[inviter_user_id], backref='sent_referrals')
    invitee = db.relationship('User', foreign_keys=[invitee_user_id], backref='received_referral')

    def to_dict(self):
        return {
            'id': self.id,
            'inviter_user_id': self.inviter_user_id,
            'invitee_user_id': self.invitee_user_id,
            'invitee_email': self.invitee_email,
            'status': self.status,
            'register_reward_granted': self.register_reward_granted,
            'register_reward_days': self.register_reward_days,
            'register_reward_at': self.register_reward_at.isoformat() if self.register_reward_at else None,
            'premium_reward_granted': self.premium_reward_granted,
            'premium_reward_days': self.premium_reward_days,
            'premium_reward_at': self.premium_reward_at.isoformat() if self.premium_reward_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def generate_referral_code(length=8):
        """生成随机邀请码"""
        alphabet = string.ascii_uppercase + string.digits
        # 排除容易混淆的字符
        alphabet = alphabet.replace('O', '').replace('0', '').replace('I', '').replace('1', '').replace('L', '')
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def __repr__(self):
        return f'<Referral inviter={self.inviter_user_id} invitee={self.invitee_user_id} status={self.status}>'
