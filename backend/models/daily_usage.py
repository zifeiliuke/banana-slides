"""
DailyUsage model - tracks daily API usage for rate limiting
"""
import uuid
from datetime import datetime, timezone, date
from . import db


class DailyUsage(db.Model):
    """
    每日用量记录模型 - 用于限制每日图片生成次数
    """
    __tablename__ = 'daily_usage'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 用户ID
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    # 日期（格式: YYYY-MM-DD）
    usage_date = db.Column(db.Date, nullable=False, index=True)

    # 图片生成次数（按页计算）
    image_generation_count = db.Column(db.Integer, nullable=False, default=0)

    # 文本生成调用次数
    text_generation_count = db.Column(db.Integer, nullable=False, default=0)

    # 总tokens消耗
    total_tokens = db.Column(db.Integer, nullable=False, default=0)

    # 是否使用了系统API（用于统计）
    used_system_api = db.Column(db.Boolean, nullable=False, default=True)

    # 时间戳
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # 唯一约束: 每个用户每天只有一条记录
    __table_args__ = (
        db.UniqueConstraint('user_id', 'usage_date', name='uq_user_date'),
    )

    # Relationships
    user = db.relationship('User', backref='daily_usages')

    @classmethod
    def get_today_usage(cls, user_id: str):
        """获取用户今日用量记录，如果不存在则创建"""
        today = date.today()
        usage = cls.query.filter_by(user_id=user_id, usage_date=today).first()
        if not usage:
            usage = cls(user_id=user_id, usage_date=today)
            db.session.add(usage)
            db.session.commit()
        return usage

    @classmethod
    def increment_image_count(cls, user_id: str, count: int = 1, used_system_api: bool = True):
        """增加图片生成计数"""
        usage = cls.get_today_usage(user_id)
        usage.image_generation_count += count
        usage.used_system_api = used_system_api
        usage.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return usage

    @classmethod
    def increment_text_count(cls, user_id: str, count: int = 1, tokens: int = 0, used_system_api: bool = True):
        """增加文本生成计数和tokens"""
        usage = cls.get_today_usage(user_id)
        usage.text_generation_count += count
        usage.total_tokens += tokens
        usage.used_system_api = used_system_api
        usage.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return usage

    @classmethod
    def get_remaining_quota(cls, user_id: str, daily_limit: int) -> int:
        """获取用户今日剩余配额"""
        usage = cls.get_today_usage(user_id)
        remaining = daily_limit - usage.image_generation_count
        return max(0, remaining)

    @classmethod
    def can_generate(cls, user_id: str, daily_limit: int, pages_count: int = 1) -> tuple:
        """
        检查用户是否可以生成指定数量的页面

        Returns:
            (can_generate: bool, remaining: int, message: str)
        """
        usage = cls.get_today_usage(user_id)
        remaining = daily_limit - usage.image_generation_count

        if remaining <= 0:
            return False, 0, 'PPT生成次数已达到上限'

        if remaining < pages_count:
            return False, remaining, f'PPT生成次数不足，今日剩余 {remaining} 页'

        return True, remaining - pages_count, ''

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'usage_date': self.usage_date.isoformat() if self.usage_date else None,
            'image_generation_count': self.image_generation_count,
            'text_generation_count': self.text_generation_count,
            'total_tokens': self.total_tokens,
            'used_system_api': self.used_system_api,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<DailyUsage user={self.user_id} date={self.usage_date} count={self.image_generation_count}>'
