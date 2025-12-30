"""
SystemSettings model - stores system-wide configuration for multi-user features
"""
import uuid
from datetime import datetime, timezone
from . import db


class SystemSettings(db.Model):
    """
    系统设置模型 - 存储多用户功能的全局配置
    使用单例模式，只有一行数据
    """
    __tablename__ = 'system_settings'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # ========== 注册设置 ==========
    # 新用户默认等级: 'free' | 'premium'
    default_user_tier = db.Column(db.String(20), nullable=False, default='free')
    # 如果默认等级是premium，默认会员天数
    default_premium_days = db.Column(db.Integer, nullable=False, default=30)
    # 是否要求邮箱验证
    require_email_verification = db.Column(db.Boolean, nullable=False, default=True)

    # ========== 裂变设置 ==========
    # 是否启用邀请裂变功能
    referral_enabled = db.Column(db.Boolean, nullable=False, default=True)
    # 被邀请用户注册后，邀请者获得的会员天数
    referral_register_reward_days = db.Column(db.Integer, nullable=False, default=1)
    # 被邀请用户注册后，被邀请者获得的会员天数
    referral_invitee_reward_days = db.Column(db.Integer, nullable=False, default=1)
    # 被邀请用户成为会员后，邀请者获得的会员天数
    referral_premium_reward_days = db.Column(db.Integer, nullable=False, default=3)
    # 邀请链接域名
    referral_domain = db.Column(db.String(200), nullable=False, default='ppt.netopstec.com')

    # ========== 用量限制设置 ==========
    # 每日图片生成限制（按页计算）
    daily_image_generation_limit = db.Column(db.Integer, nullable=False, default=20)
    # 是否启用用量限制
    enable_usage_limit = db.Column(db.Boolean, nullable=False, default=True)

    # ========== SMTP邮件设置 ==========
    smtp_host = db.Column(db.String(200), nullable=True)
    smtp_port = db.Column(db.Integer, nullable=True, default=465)
    smtp_user = db.Column(db.String(200), nullable=True)
    smtp_password = db.Column(db.String(500), nullable=True)
    smtp_use_ssl = db.Column(db.Boolean, nullable=False, default=True)
    smtp_sender_name = db.Column(db.String(100), nullable=True, default='Banana Slides')

    # ========== 时间戳 ==========
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    @classmethod
    def get_settings(cls):
        """获取系统设置（单例模式）"""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

    def to_dict(self, include_sensitive=False):
        """转换为字典"""
        data = {
            'id': self.id,
            # 注册设置
            'default_user_tier': self.default_user_tier,
            'default_premium_days': self.default_premium_days,
            'require_email_verification': self.require_email_verification,
            # 裂变设置
            'referral_enabled': self.referral_enabled,
            'referral_register_reward_days': self.referral_register_reward_days,
            'referral_invitee_reward_days': self.referral_invitee_reward_days,
            'referral_premium_reward_days': self.referral_premium_reward_days,
            'referral_domain': self.referral_domain,
            # 用量限制
            'daily_image_generation_limit': self.daily_image_generation_limit,
            'enable_usage_limit': self.enable_usage_limit,
            # SMTP设置（不含密码）
            'smtp_host': self.smtp_host,
            'smtp_port': self.smtp_port,
            'smtp_user': self.smtp_user,
            'smtp_use_ssl': self.smtp_use_ssl,
            'smtp_sender_name': self.smtp_sender_name,
            'smtp_configured': bool(self.smtp_host and self.smtp_user and self.smtp_password),
            # 时间戳
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_sensitive:
            data['smtp_password'] = self.smtp_password

        return data

    def __repr__(self):
        return f'<SystemSettings id={self.id}>'
