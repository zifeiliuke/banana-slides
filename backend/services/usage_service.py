"""
Usage Service - handles API usage tracking and limits
"""
import logging
from typing import Tuple
from models import User, DailyUsage, SystemSettings, UserSettings

logger = logging.getLogger(__name__)


class UsageService:
    """API使用量服务"""

    @staticmethod
    def is_using_system_api(user: User) -> bool:
        """
        检查用户是否使用系统API

        Args:
            user: 用户对象

        Returns:
            True 表示使用系统API，False 表示使用自己的API
        """
        # 管理员始终使用系统API
        if user.is_admin():
            return True

        # 高级会员使用系统API
        if user.is_premium_active():
            return True

        # 免费用户检查是否配置了自己的API
        user_settings = UserSettings.query.filter_by(user_id=user.id).first()
        if user_settings and user_settings.has_api_key():
            return False  # 使用自己的API

        # 没有配置API的免费用户会在调用时报错，这里返回True
        return True

    @staticmethod
    def check_image_generation_quota(user: User, pages_count: int = 1) -> Tuple[bool, int, str]:
        """
        检查用户是否可以生成指定数量的图片

        Args:
            user: 用户对象
            pages_count: 要生成的页数

        Returns:
            (can_generate: bool, remaining: int, error_message: str)
        """
        # 获取系统设置
        settings = SystemSettings.get_settings()

        # 如果未启用限制，直接通过
        if not settings.enable_usage_limit:
            return True, -1, ''  # -1 表示无限制

        # 管理员不受限制
        if user.is_admin():
            return True, -1, ''

        # 检查用户是否使用系统API
        if not UsageService.is_using_system_api(user):
            # 使用自己的API，不受限制
            return True, -1, ''

        # 使用系统API，检查配额
        daily_limit = settings.daily_image_generation_limit
        can_generate, remaining, message = DailyUsage.can_generate(
            user.id, daily_limit, pages_count
        )

        return can_generate, remaining, message

    @staticmethod
    def record_image_generation(user: User, pages_count: int = 1):
        """
        记录图片生成使用量

        Args:
            user: 用户对象
            pages_count: 生成的页数
        """
        # 检查是否使用系统API
        using_system_api = UsageService.is_using_system_api(user)

        # 只有使用系统API才记录
        if using_system_api:
            DailyUsage.increment_image_count(
                user.id,
                count=pages_count,
                used_system_api=True
            )
            logger.info(f"Recorded {pages_count} image generations for user {user.username}")

    @staticmethod
    def record_text_generation(user: User, tokens: int = 0):
        """
        记录文本生成使用量

        Args:
            user: 用户对象
            tokens: 消耗的tokens数量
        """
        # 检查是否使用系统API
        using_system_api = UsageService.is_using_system_api(user)

        # 只有使用系统API才记录
        if using_system_api:
            DailyUsage.increment_text_count(
                user.id,
                count=1,
                tokens=tokens,
                used_system_api=True
            )
            logger.info(f"Recorded text generation for user {user.username}, tokens: {tokens}")

    @staticmethod
    def get_user_usage_status(user: User) -> dict:
        """
        获取用户的使用状态

        Args:
            user: 用户对象

        Returns:
            使用状态字典
        """
        settings = SystemSettings.get_settings()
        using_system_api = UsageService.is_using_system_api(user)

        if not settings.enable_usage_limit or user.is_admin() or not using_system_api:
            return {
                'limited': False,
                'daily_limit': -1,
                'used_today': 0,
                'remaining': -1,
                'using_system_api': using_system_api,
            }

        usage = DailyUsage.get_today_usage(user.id)
        daily_limit = settings.daily_image_generation_limit
        remaining = max(0, daily_limit - usage.image_generation_count)

        return {
            'limited': True,
            'daily_limit': daily_limit,
            'used_today': usage.image_generation_count,
            'remaining': remaining,
            'using_system_api': using_system_api,
        }


def check_and_record_usage(user: User, pages_count: int = 1) -> Tuple[bool, str]:
    """
    检查并记录使用量（便捷函数）

    Args:
        user: 用户对象
        pages_count: 要生成的页数

    Returns:
        (success: bool, error_message: str)
    """
    can_generate, remaining, message = UsageService.check_image_generation_quota(user, pages_count)

    if not can_generate:
        return False, message

    # 注意：这里不记录，只检查。记录在实际生成成功后进行。
    return True, ''
