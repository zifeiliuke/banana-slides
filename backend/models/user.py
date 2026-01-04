"""
User model - stores user account information
"""
import uuid
import secrets
import string
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class User(db.Model):
    """
    User model - represents a user account
    """
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'user' | 'admin'
    tier = db.Column(db.String(20), nullable=False, default='free')  # 'free' | 'premium'
    premium_expires_at = db.Column(db.DateTime, nullable=True)  # 高级会员过期时间
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)

    # ========== 邀请裂变相关字段 ==========
    # 用户专属邀请码（注册时自动生成）
    referral_code = db.Column(db.String(16), unique=True, nullable=True, index=True)
    # 通过谁的邀请注册（邀请者用户ID）
    referred_by_user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)

    # ========== 邮箱验证相关字段 ==========
    # 邮箱是否已验证
    email_verified = db.Column(db.Boolean, nullable=False, default=False)

    # Relationships
    projects = db.relationship('Project', back_populates='user', lazy='dynamic',
                              cascade='all, delete-orphan')
    templates = db.relationship('UserTemplate', back_populates='user', lazy='dynamic',
                               cascade='all, delete-orphan')
    settings = db.relationship('UserSettings', back_populates='user', uselist=False,
                              cascade='all, delete-orphan')
    # 邀请关系
    referred_by = db.relationship('User', remote_side=[id], backref='referrals_made')

    def set_password(self, password: str):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)

    def is_premium_active(self) -> bool:
        """Check if user has active premium subscription"""
        if self.tier != 'premium':
            return False
        # If no expiration date, it's permanent premium (e.g., admin)
        if self.premium_expires_at is None:
            return True
        # Ensure timezone-aware comparison
        now = datetime.now(timezone.utc)
        expires_at = self.premium_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > now

    def is_admin(self) -> bool:
        """Check if user is admin"""
        return self.role == 'admin'

    def get_effective_tier(self) -> str:
        """
        获取用户实际有效的会员等级

        如果用户 tier 是 premium 但会员已过期，返回 'free'
        否则返回数据库存储的 tier 值
        """
        if self.tier == 'premium' and not self.is_premium_active():
            return 'free'
        return self.tier

    def to_dict(self, include_sensitive=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'email_verified': self.email_verified,
            'role': self.role,
            'tier': self.get_effective_tier(),  # 返回实际有效的会员等级
            'stored_tier': self.tier,  # 数据库存储的原始等级（管理用）
            'is_premium_active': self.is_premium_active(),
            'premium_expires_at': self.premium_expires_at.isoformat() if self.premium_expires_at else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'referral_code': self.referral_code,
            'referred_by_user_id': self.referred_by_user_id,
        }

        if include_sensitive:
            data['updated_at'] = self.updated_at.isoformat() if self.updated_at else None

        return data

    @staticmethod
    def generate_referral_code(length=8):
        """生成随机邀请码"""
        alphabet = string.ascii_uppercase + string.digits
        # 排除容易混淆的字符
        alphabet = alphabet.replace('O', '').replace('0', '').replace('I', '').replace('1', '').replace('L', '')
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def ensure_referral_code(self):
        """确保用户有邀请码，如果没有则生成"""
        if not self.referral_code:
            # 生成唯一邀请码
            for _ in range(10):  # 最多尝试10次
                code = self.generate_referral_code()
                if not User.query.filter_by(referral_code=code).first():
                    self.referral_code = code
                    break
        return self.referral_code

    def add_premium_days(self, days: int):
        """
        增加会员天数

        Args:
            days: 要增加的天数
        """
        now = datetime.now(timezone.utc)

        if self.tier == 'premium' and self.premium_expires_at:
            # 已是会员，在现有基础上延长
            expires_at = self.premium_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at > now:
                self.premium_expires_at = expires_at + timedelta(days=days)
            else:
                self.premium_expires_at = now + timedelta(days=days)
        else:
            # 新开通会员
            self.premium_expires_at = now + timedelta(days=days)

        self.tier = 'premium'
        self.updated_at = now

    def __repr__(self):
        return f'<User {self.username} ({self.role}/{self.tier})>'
