"""
EmailVerification model - stores email verification codes for registration
"""
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from . import db


class EmailVerification(db.Model):
    """
    邮箱验证码模型 - 用于注册时的邮箱验证
    """
    __tablename__ = 'email_verifications'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 邮箱地址
    email = db.Column(db.String(100), nullable=False, index=True)
    # 6位验证码
    code = db.Column(db.String(6), nullable=False)
    # 过期时间（默认10分钟）
    expires_at = db.Column(db.DateTime, nullable=False)
    # 是否已使用
    is_used = db.Column(db.Boolean, nullable=False, default=False)
    # 使用时间
    used_at = db.Column(db.DateTime, nullable=True)
    # 尝试次数（防止暴力破解）
    attempts = db.Column(db.Integer, nullable=False, default=0)

    # 时间戳
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def generate_code():
        """生成6位数字验证码"""
        return ''.join(secrets.choice('0123456789') for _ in range(6))

    @classmethod
    def create_verification(cls, email: str, expires_minutes: int = 10):
        """
        创建新的验证码

        Args:
            email: 邮箱地址
            expires_minutes: 过期时间（分钟）

        Returns:
            EmailVerification 实例
        """
        # 先将该邮箱之前未使用的验证码标记为已使用（失效）
        cls.query.filter_by(email=email, is_used=False).update({'is_used': True})

        # 创建新验证码
        verification = cls(
            email=email.lower().strip(),
            code=cls.generate_code(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        )
        db.session.add(verification)
        db.session.commit()
        return verification

    @classmethod
    def verify_code(cls, email: str, code: str) -> tuple:
        """
        验证邮箱验证码

        Args:
            email: 邮箱地址
            code: 验证码

        Returns:
            (success: bool, message: str)
        """
        email = email.lower().strip()

        # 查找最新的未使用验证码
        verification = cls.query.filter_by(
            email=email,
            is_used=False
        ).order_by(cls.created_at.desc()).first()

        if not verification:
            return False, '验证码不存在或已过期'

        # 增加尝试次数
        verification.attempts += 1
        db.session.commit()

        # 检查尝试次数
        if verification.attempts > 5:
            verification.is_used = True
            db.session.commit()
            return False, '验证码尝试次数过多，请重新获取'

        # 检查是否过期
        now = datetime.now(timezone.utc)
        expires_at = verification.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            return False, '验证码已过期'

        # 验证码匹配
        if verification.code != code:
            return False, '验证码错误'

        # 标记为已使用
        verification.is_used = True
        verification.used_at = now
        db.session.commit()

        return True, '验证成功'

    @classmethod
    def can_send_new_code(cls, email: str, cooldown_seconds: int = 60) -> tuple:
        """
        检查是否可以发送新验证码（防止频繁发送）

        Args:
            email: 邮箱地址
            cooldown_seconds: 冷却时间（秒）

        Returns:
            (can_send: bool, wait_seconds: int)
        """
        email = email.lower().strip()

        # 查找最近发送的验证码
        recent = cls.query.filter_by(email=email).order_by(cls.created_at.desc()).first()

        if not recent:
            return True, 0

        now = datetime.now(timezone.utc)
        created_at = recent.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        elapsed = (now - created_at).total_seconds()

        if elapsed < cooldown_seconds:
            wait_seconds = int(cooldown_seconds - elapsed)
            return False, wait_seconds

        return True, 0

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_used': self.is_used,
            'attempts': self.attempts,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<EmailVerification email={self.email} code={self.code} used={self.is_used}>'
