"""
User model - stores user account information
"""
import uuid
from datetime import datetime, timezone
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

    # Relationships
    projects = db.relationship('Project', back_populates='user', lazy='dynamic',
                              cascade='all, delete-orphan')
    templates = db.relationship('UserTemplate', back_populates='user', lazy='dynamic',
                               cascade='all, delete-orphan')
    settings = db.relationship('UserSettings', back_populates='user', uselist=False,
                              cascade='all, delete-orphan')

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

    def to_dict(self, include_sensitive=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'tier': self.tier,
            'is_premium_active': self.is_premium_active(),
            'premium_expires_at': self.premium_expires_at.isoformat() if self.premium_expires_at else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
        }

        if include_sensitive:
            data['updated_at'] = self.updated_at.isoformat() if self.updated_at else None

        return data

    def __repr__(self):
        return f'<User {self.username} ({self.role}/{self.tier})>'
