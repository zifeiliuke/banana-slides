"""
Recharge Code model for premium upgrades
"""
import uuid
from datetime import datetime
from models import db


class RechargeCode(db.Model):
    """充值码模型"""
    __tablename__ = 'recharge_codes'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    duration_days = db.Column(db.Integer, nullable=False)  # 充值天数
    is_used = db.Column(db.Boolean, nullable=False, default=False, index=True)
    used_by_user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_by_admin_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # 充值码过期时间

    # Relationships
    used_by_user = db.relationship('User', foreign_keys=[used_by_user_id], backref='used_codes')
    created_by_admin = db.relationship('User', foreign_keys=[created_by_admin_id], backref='created_codes')

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'duration_days': self.duration_days,
            'is_used': self.is_used,
            'used_by_user_id': self.used_by_user_id,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'created_by_admin_id': self.created_by_admin_id,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }

    @staticmethod
    def generate_code(length=16):
        """生成随机充值码"""
        import secrets
        import string
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))


class PremiumHistory(db.Model):
    """会员历史记录"""
    __tablename__ = 'premium_history'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False)  # 'recharge', 'admin_grant', 'admin_revoke', 'expired'
    duration_days = db.Column(db.Integer, nullable=True)
    recharge_code_id = db.Column(db.String(36), db.ForeignKey('recharge_codes.id'), nullable=True)
    admin_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    note = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='premium_history')
    admin = db.relationship('User', foreign_keys=[admin_id])
    recharge_code = db.relationship('RechargeCode', backref='history')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'duration_days': self.duration_days,
            'recharge_code_id': self.recharge_code_id,
            'admin_id': self.admin_id,
            'note': self.note,
            'created_at': self.created_at.isoformat(),
        }
