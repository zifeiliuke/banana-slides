"""
Referral Service - handles referral rewards and tracking (积分版)
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from models import db, User, Referral, SystemSettings
from services.points_service import PointsService

logger = logging.getLogger(__name__)


class ReferralService:
    """邀请裂变服务（积分版）"""

    @staticmethod
    def get_inviter_by_code(referral_code: str) -> Optional[User]:
        """
        通过邀请码获取邀请者

        Args:
            referral_code: 邀请码

        Returns:
            邀请者用户对象，如果不存在返回None
        """
        if not referral_code:
            return None
        return User.query.filter_by(referral_code=referral_code.upper()).first()

    @staticmethod
    def process_registration_referral(invitee: User, referral_code: str) -> Tuple[bool, str]:
        """
        处理注册时的邀请关系（积分奖励）

        Args:
            invitee: 新注册的用户
            referral_code: 邀请码

        Returns:
            (success: bool, message: str)
        """
        if not referral_code:
            return True, ''

        # 检查裂变功能是否启用
        settings = SystemSettings.get_settings()
        if not settings.referral_enabled:
            return True, '邀请活动暂未开启'

        inviter = ReferralService.get_inviter_by_code(referral_code)
        if not inviter:
            logger.warning(f"Invalid referral code: {referral_code}")
            return True, '邀请码无效，但注册成功'  # 邀请码无效不影响注册

        if inviter.id == invitee.id:
            return True, '不能使用自己的邀请码'

        # 记录邀请关系
        invitee.referred_by_user_id = inviter.id

        # 创建邀请记录
        referral = Referral(
            inviter_user_id=inviter.id,
            invitee_user_id=invitee.id,
            invitee_email=invitee.email,
            status='registered'
        )
        db.session.add(referral)

        # 发放邀请者注册奖励（积分）
        inviter_reward_points = settings.referral_inviter_register_points

        if inviter_reward_points > 0:
            PointsService.grant_referral_reward(
                user_id=inviter.id,
                reward_type='inviter_register',
                invitee_username=invitee.username
            )

            # 更新邀请记录
            referral.register_reward_granted = True
            referral.register_reward_days = inviter_reward_points  # 复用字段存积分
            referral.register_reward_at = datetime.now(timezone.utc)

            logger.info(f"Granted {inviter_reward_points} points to inviter {inviter.username} for inviting {invitee.username}")

            # 尝试发送邮件通知邀请者
            try:
                if inviter.email:
                    from services.email_service import get_email_service
                    email_service = get_email_service()
                    email_service.send_referral_reward_notification(
                        inviter.email, invitee.username, inviter_reward_points, 'register'
                    )
            except Exception as e:
                logger.warning(f"Failed to send referral reward email to inviter: {e}")

        # 发放被邀请者注册奖励（积分）
        invitee_reward_points = settings.referral_invitee_register_points

        if invitee_reward_points > 0:
            PointsService.grant_referral_reward(
                user_id=invitee.id,
                reward_type='invitee_register',
                invitee_username=inviter.username
            )

            logger.info(f"Granted {invitee_reward_points} points to invitee {invitee.username} for registering via referral")

        return True, ''

    @staticmethod
    def process_premium_upgrade_referral(user: User):
        """
        处理用户首次充值时的邀请奖励（积分版）

        Args:
            user: 充值的用户
        """
        if not user.referred_by_user_id:
            return

        # 检查裂变功能是否启用
        settings = SystemSettings.get_settings()
        if not settings.referral_enabled:
            return

        # 查找邀请记录（只奖励一次）
        referral = Referral.query.filter_by(
            inviter_user_id=user.referred_by_user_id,
            invitee_user_id=user.id,
            premium_reward_granted=False
        ).first()

        if not referral:
            return

        # 获取邀请者
        inviter = User.query.get(user.referred_by_user_id)
        if not inviter:
            return

        # 发放升级奖励（积分）
        reward_points = settings.referral_inviter_upgrade_points

        if reward_points > 0:
            PointsService.grant_referral_reward(
                user_id=inviter.id,
                reward_type='inviter_upgrade',
                invitee_username=user.username
            )

            # 更新邀请记录
            referral.status = 'premium'
            referral.premium_reward_granted = True
            referral.premium_reward_days = reward_points  # 复用字段存积分
            referral.premium_reward_at = datetime.now(timezone.utc)

            db.session.commit()

            logger.info(f"Granted {reward_points} points to {inviter.username} for {user.username} upgrading to premium")

            # 尝试发送邮件通知
            try:
                if inviter.email:
                    from services.email_service import get_email_service
                    email_service = get_email_service()
                    email_service.send_referral_reward_notification(
                        inviter.email, user.username, reward_points, 'premium'
                    )
            except Exception as e:
                logger.warning(f"Failed to send referral reward email: {e}")

    @staticmethod
    def get_user_referral_stats(user: User) -> dict:
        """
        获取用户的邀请统计（积分版）

        Args:
            user: 用户对象

        Returns:
            邀请统计字典
        """
        # 确保用户有邀请码
        if not user.referral_code:
            user.ensure_referral_code()
            db.session.commit()

        settings = SystemSettings.get_settings()

        # 检查裂变功能是否启用
        if not settings.referral_enabled:
            return {
                'referral_enabled': False,
                'referral_code': user.referral_code,
                'referral_link': f'https://{settings.referral_domain}/register?ref={user.referral_code}',
                'total_invites': 0,
                'registered_invites': 0,
                'premium_invites': 0,
                'total_reward_points': 0,
                'register_reward_points': 0,
                'premium_reward_points': 0,
            }

        # 统计邀请数据
        total_invites = Referral.query.filter_by(inviter_user_id=user.id).count()
        registered_invites = Referral.query.filter(
            Referral.inviter_user_id == user.id,
            Referral.status.in_(['registered', 'premium'])
        ).count()
        premium_invites = Referral.query.filter_by(
            inviter_user_id=user.id,
            status='premium'
        ).count()

        # 计算总奖励积分
        total_reward_points = 0
        referrals = Referral.query.filter_by(inviter_user_id=user.id).all()
        for ref in referrals:
            if ref.register_reward_days:  # 复用字段存积分
                total_reward_points += ref.register_reward_days
            if ref.premium_reward_days:  # 复用字段存积分
                total_reward_points += ref.premium_reward_days

        return {
            'referral_enabled': True,
            'referral_code': user.referral_code,
            'referral_link': f'https://{settings.referral_domain}/register?ref={user.referral_code}',
            'total_invites': total_invites,
            'registered_invites': registered_invites,
            'premium_invites': premium_invites,
            # 积分奖励数据
            'total_reward_points': total_reward_points,
            'register_reward_points': settings.referral_inviter_register_points,
            'invitee_register_reward_points': settings.referral_invitee_register_points,
            'premium_reward_points': settings.referral_inviter_upgrade_points,
            # 兼容旧字段名（前端使用）
            'total_reward_days': total_reward_points,
            'register_reward_days': settings.referral_inviter_register_points,
            'invitee_register_reward_days': settings.referral_invitee_register_points,
            'premium_reward_days': settings.referral_inviter_upgrade_points,
        }

    @staticmethod
    def get_user_referral_list(user: User, page: int = 1, per_page: int = 20) -> dict:
        """
        获取用户的邀请列表

        Args:
            user: 用户对象
            page: 页码
            per_page: 每页数量

        Returns:
            邀请列表分页数据
        """
        query = Referral.query.filter_by(inviter_user_id=user.id).order_by(Referral.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        referrals = []
        for ref in pagination.items:
            invitee = User.query.get(ref.invitee_user_id) if ref.invitee_user_id else None
            referrals.append({
                'id': ref.id,
                'invitee_username': invitee.username if invitee else None,
                'invitee_email': ref.invitee_email,
                'status': ref.status,
                'register_reward_granted': ref.register_reward_granted,
                'register_reward_points': ref.register_reward_days,  # 复用字段
                'premium_reward_granted': ref.premium_reward_granted,
                'premium_reward_points': ref.premium_reward_days,  # 复用字段
                'created_at': ref.created_at.isoformat() if ref.created_at else None,
            })

        return {
            'referrals': referrals,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
        }
