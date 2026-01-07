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
    # 是否要求邮箱验证
    require_email_verification = db.Column(db.Boolean, nullable=False, default=True)

    # ========== 积分配置（新） ==========
    # 积分消耗：每页PPT消耗积分数
    points_per_page = db.Column(db.Integer, nullable=False, default=15)

    # 注册赠送积分
    register_bonus_points = db.Column(db.Integer, nullable=False, default=300)
    # 注册赠送积分有效期（天），NULL表示永不过期
    register_bonus_expire_days = db.Column(db.Integer, nullable=True, default=3)

    # ========== 裂变设置（积分化） ==========
    # 是否启用邀请裂变功能
    referral_enabled = db.Column(db.Boolean, nullable=False, default=True)
    # 邀请链接域名
    referral_domain = db.Column(db.String(200), nullable=False, default='ppt.netopstec.com')

    # 邀请者注册奖励积分（被邀请者注册后，邀请者获得）
    referral_inviter_register_points = db.Column(db.Integer, nullable=False, default=100)
    # 被邀请者注册奖励积分
    referral_invitee_register_points = db.Column(db.Integer, nullable=False, default=100)
    # 邀请者升级奖励积分（被邀请者首次充值后，邀请者获得）
    referral_inviter_upgrade_points = db.Column(db.Integer, nullable=False, default=450)
    # 邀请奖励积分有效期（天），NULL表示永不过期
    referral_points_expire_days = db.Column(db.Integer, nullable=True, default=None)

    # ========== 兼容旧字段（迁移后可删除） ==========
    default_user_tier = db.Column(db.String(20), nullable=True, default='free')  # [废弃]
    default_premium_days = db.Column(db.Integer, nullable=True, default=30)  # [废弃]
    referral_register_reward_days = db.Column(db.Integer, nullable=True, default=1)  # [废弃]
    referral_invitee_reward_days = db.Column(db.Integer, nullable=True, default=1)  # [废弃]
    referral_premium_reward_days = db.Column(db.Integer, nullable=True, default=3)  # [废弃]
    daily_image_generation_limit = db.Column(db.Integer, nullable=True, default=20)  # [废弃]
    enable_usage_limit = db.Column(db.Boolean, nullable=True, default=True)  # [废弃]

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
            'require_email_verification': self.require_email_verification,
            # 积分配置（新）
            'points_per_page': self.points_per_page,
            'register_bonus_points': self.register_bonus_points,
            'register_bonus_expire_days': self.register_bonus_expire_days,
            # 裂变设置（积分化）
            'referral_enabled': self.referral_enabled,
            'referral_domain': self.referral_domain,
            'referral_inviter_register_points': self.referral_inviter_register_points,
            'referral_invitee_register_points': self.referral_invitee_register_points,
            'referral_inviter_upgrade_points': self.referral_inviter_upgrade_points,
            'referral_points_expire_days': self.referral_points_expire_days,
            # 兼容旧字段（迁移期间保留）
            'default_user_tier': self.default_user_tier,
            'default_premium_days': self.default_premium_days,
            'referral_register_reward_days': self.referral_register_reward_days,
            'referral_invitee_reward_days': self.referral_invitee_reward_days,
            'referral_premium_reward_days': self.referral_premium_reward_days,
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
