"""
UserSettings model - stores user-specific AI configuration
"""
import uuid
from datetime import datetime, timezone
from . import db


class UserSettings(db.Model):
    """
    UserSettings model - stores individual user's AI configuration
    Free users must configure their own API Key here.
    Premium users can use global Settings instead.
    """
    __tablename__ = 'user_settings'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'),
                       unique=True, nullable=False, index=True)

    # AI Provider Configuration
    ai_provider_format = db.Column(db.String(20), nullable=False, default='gemini')  # 'gemini' | 'openai'
    api_base_url = db.Column(db.String(500), nullable=True)
    api_key = db.Column(db.String(500), nullable=True)

    # Model Configuration
    text_model = db.Column(db.String(100), nullable=True)
    image_model = db.Column(db.String(100), nullable=True)
    image_caption_model = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', back_populates='settings')

    def has_api_key(self) -> bool:
        """Check if user has configured API key"""
        return bool(self.api_key and self.api_key.strip())

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ai_provider_format': self.ai_provider_format,
            'api_base_url': self.api_base_url,
            'api_key_configured': self.has_api_key(),
            'api_key_length': len(self.api_key) if self.api_key else 0,
            'text_model': self.text_model,
            'image_model': self.image_model,
            'image_caption_model': self.image_caption_model,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_ai_config(self):
        """Convert to AI configuration dict for AIService"""
        return {
            'ai_provider_format': self.ai_provider_format,
            'api_base_url': self.api_base_url,
            'api_key': self.api_key,
            'text_model': self.text_model,
            'image_model': self.image_model,
            'image_caption_model': self.image_caption_model,
        }

    def __repr__(self):
        return f'<UserSettings user_id={self.user_id}>'
