"""
Usage Service - handles API usage tracking and points consumption
"""
import logging
from typing import Tuple
from models import User, DailyUsage, SystemSettings, UserSettings
from services.points_service import PointsService

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

        # 检查用户是否有有效积分（会员）
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
        检查用户是否可以生成指定数量的图片（基于积分）

        Args:
            user: 用户对象
            pages_count: 要生成的页数

        Returns:
            (can_generate: bool, remaining: int, error_message: str)
        """
        # 管理员不受限制
        if user.is_admin():
            return True, -1, ''

        # 检查用户是否使用系统API
        if not UsageService.is_using_system_api(user):
            # 使用自己的API，不受限制
            return True, -1, ''

        # 使用系统API，检查积分
        settings = SystemSettings.get_settings()
        required_points = settings.points_per_page * pages_count

        valid_points = PointsService.get_valid_points(user.id)

        if valid_points <= 0:
            return False, 0, '积分不足，请充值后继续使用'

        # 计算可生成页数
        can_generate_pages = valid_points // settings.points_per_page if settings.points_per_page > 0 else 0

        return True, valid_points, ''

    @staticmethod
    def consume_and_record(user: User, pages_count: int = 1) -> Tuple[bool, str]:
        """
        消耗积分并记录使用量

        Args:
            user: 用户对象
            pages_count: 生成的页数

        Returns:
            (success: bool, error_message: str)
        """
        # 管理员不消耗积分
        if user.is_admin():
            # 仍然记录使用量（用于统计）
            DailyUsage.increment_image_count(user.id, count=pages_count, used_system_api=True)
            return True, ''

        # 检查是否使用系统API
        using_system_api = UsageService.is_using_system_api(user)

        if not using_system_api:
            # 使用自己的API，只记录不消耗积分
            DailyUsage.increment_image_count(user.id, count=pages_count, used_system_api=False)
            return True, ''

        # 使用系统API，消耗积分
        settings = SystemSettings.get_settings()
        amount = settings.points_per_page * pages_count

        # 检查是否可以消费
        can_consume, remaining, message = PointsService.can_consume(user.id, amount)

        if not can_consume:
            return False, message

        # 消耗积分
        success, message = PointsService.consume_points(
            user.id,
            amount,
            f'生成 {pages_count} 页PPT'
        )

        if success:
            # 记录使用量
            DailyUsage.increment_image_count(user.id, count=pages_count, used_system_api=True)
            logger.info(f"Consumed {amount} points for {pages_count} pages, user={user.username}")

        return success, message

    @staticmethod
    def record_image_generation(user: User, pages_count: int = 1):
        """
        [兼容旧代码] 记录图片生成使用量
        新代码请使用 consume_and_record

        Args:
            user: 用户对象
            pages_count: 生成的页数
        """
        using_system_api = UsageService.is_using_system_api(user)
        DailyUsage.increment_image_count(user.id, count=pages_count, used_system_api=using_system_api)
        logger.info(f"Recorded {pages_count} image generations for user {user.username}")

    @staticmethod
    def record_text_generation(user: User, tokens: int = 0):
        """
        记录文本生成使用量（文本生成不消耗积分）

        Args:
            user: 用户对象
            tokens: 消耗的tokens数量
        """
        using_system_api = UsageService.is_using_system_api(user)

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
        获取用户的使用状态（基于积分）

        Args:
            user: 用户对象

        Returns:
            使用状态字典
        """
        using_system_api = UsageService.is_using_system_api(user)
        settings = SystemSettings.get_settings()

        if user.is_admin():
            return {
                'limited': False,
                'valid_points': -1,  # 无限
                'points_per_page': settings.points_per_page,
                'can_generate_pages': -1,
                'using_system_api': True,
                'is_admin': True,
            }

        if not using_system_api:
            return {
                'limited': False,
                'valid_points': -1,
                'points_per_page': settings.points_per_page,
                'can_generate_pages': -1,
                'using_system_api': False,
                'is_admin': False,
            }

        # 使用系统API，返回积分信息
        valid_points = PointsService.get_valid_points(user.id)
        can_generate_pages = valid_points // settings.points_per_page if settings.points_per_page > 0 else 0
        expiring = PointsService.get_expiring_points(user.id)

        return {
            'limited': valid_points <= 0,
            'valid_points': valid_points,
            'points_per_page': settings.points_per_page,
            'can_generate_pages': can_generate_pages,
            'expiring_soon': expiring,
            'using_system_api': True,
            'is_admin': False,
        }


def check_and_record_usage(user: User, pages_count: int = 1) -> Tuple[bool, str]:
    """
    检查使用配额（便捷函数）
    注意：此函数只检查不消耗，实际消耗在生成成功后调用 consume_and_record

    Args:
        user: 用户对象
        pages_count: 要生成的页数

    Returns:
        (success: bool, error_message: str)
    """
    can_generate, remaining, message = UsageService.check_image_generation_quota(user, pages_count)

    if not can_generate:
        return False, message

    return True, ''
