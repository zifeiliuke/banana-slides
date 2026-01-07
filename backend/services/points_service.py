"""
Points Service - 积分核心服务
处理积分的发放、消耗、查询等核心逻辑
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List
from sqlalchemy import func, or_, case

from models import db, User, PointsBalance, PointsTransaction, SystemSettings

logger = logging.getLogger(__name__)


class PointsService:
    """积分服务"""

    # ========== 积分查询 ==========

    @staticmethod
    def get_valid_points(user_id: str) -> int:
        """
        获取用户当前有效积分总数

        Args:
            user_id: 用户ID

        Returns:
            有效积分总数
        """
        now = datetime.now(timezone.utc)
        total = db.session.query(func.sum(PointsBalance.remaining)).filter(
            PointsBalance.user_id == user_id,
            PointsBalance.remaining > 0,
            or_(
                PointsBalance.expires_at.is_(None),  # 永不过期
                PointsBalance.expires_at > now  # 未过期
            )
        ).scalar()
        return total or 0

    @staticmethod
    def get_expiring_points(user_id: str, days: int = 7) -> dict:
        """
        获取即将过期的积分信息

        Args:
            user_id: 用户ID
            days: 天数（默认7天内）

        Returns:
            {
                'points': 即将过期积分数,
                'earliest_expire': 最早过期时间
            }
        """
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=days)

        balances = PointsBalance.query.filter(
            PointsBalance.user_id == user_id,
            PointsBalance.remaining > 0,
            PointsBalance.expires_at.isnot(None),
            PointsBalance.expires_at > now,
            PointsBalance.expires_at <= deadline
        ).order_by(PointsBalance.expires_at.asc()).all()

        total_expiring = sum(b.remaining for b in balances)
        earliest = balances[0].expires_at if balances else None

        return {
            'points': total_expiring,
            'days': days,
            'earliest_expire': earliest.isoformat() if earliest else None
        }

    @staticmethod
    def get_points_balances(user_id: str, include_expired: bool = False) -> List[PointsBalance]:
        """
        获取用户的积分批次列表

        Args:
            user_id: 用户ID
            include_expired: 是否包含已过期的批次

        Returns:
            积分批次列表
        """
        query = PointsBalance.query.filter_by(user_id=user_id)

        if not include_expired:
            now = datetime.now(timezone.utc)
            query = query.filter(
                PointsBalance.remaining > 0,
                or_(
                    PointsBalance.expires_at.is_(None),
                    PointsBalance.expires_at > now
                )
            )

        return query.order_by(PointsBalance.created_at.desc()).all()

    @staticmethod
    def get_transactions(
        user_id: str,
        type_filter: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> dict:
        """
        获取积分流水记录

        Args:
            user_id: 用户ID
            type_filter: 类型筛选 (income/expense/expired)
            page: 页码
            per_page: 每页数量

        Returns:
            分页数据
        """
        query = PointsTransaction.query.filter_by(user_id=user_id)

        if type_filter:
            query = query.filter_by(type=type_filter)

        query = query.order_by(PointsTransaction.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            'transactions': [t.to_dict() for t in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }

    # ========== 积分发放 ==========

    @staticmethod
    def grant_points(
        user_id: str,
        amount: int,
        source: str,
        source_id: Optional[str] = None,
        source_note: Optional[str] = None,
        expire_days: Optional[int] = None
    ) -> PointsBalance:
        """
        发放积分

        Args:
            user_id: 用户ID
            amount: 积分数量
            source: 来源类型
            source_id: 关联ID（如充值码ID）
            source_note: 备注说明
            expire_days: 有效期天数，None表示永不过期

        Returns:
            创建的积分批次对象
        """
        expires_at = None
        if expire_days is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expire_days)

        balance = PointsBalance(
            user_id=user_id,
            amount=amount,
            remaining=amount,
            source=source,
            source_id=source_id,
            source_note=source_note,
            expires_at=expires_at
        )
        db.session.add(balance)
        db.session.flush()  # 获取ID

        # 计算新的有效积分总数
        new_valid_points = PointsService.get_valid_points(user_id)

        # 记录流水
        transaction = PointsTransaction(
            user_id=user_id,
            type=PointsTransaction.TYPE_INCOME,
            amount=amount,
            balance_after=new_valid_points,
            balance_id=balance.id,
            description=PointsBalance.get_source_display(source)
        )
        db.session.add(transaction)

        logger.info(f"Granted {amount} points to user {user_id}, source={source}, expire_days={expire_days}")

        return balance

    @staticmethod
    def grant_register_bonus(user_id: str) -> Optional[PointsBalance]:
        """
        发放注册赠送积分

        Args:
            user_id: 用户ID

        Returns:
            创建的积分批次对象，如果赠送积分为0则返回None
        """
        settings = SystemSettings.get_settings()

        if settings.register_bonus_points <= 0:
            return None

        return PointsService.grant_points(
            user_id=user_id,
            amount=settings.register_bonus_points,
            source=PointsBalance.SOURCE_REGISTER,
            source_note='新用户注册赠送',
            expire_days=settings.register_bonus_expire_days
        )

    @staticmethod
    def grant_referral_reward(
        user_id: str,
        reward_type: str,
        invitee_username: str
    ) -> Optional[PointsBalance]:
        """
        发放邀请奖励积分

        Args:
            user_id: 用户ID
            reward_type: 奖励类型 ('inviter_register', 'invitee_register', 'inviter_upgrade')
            invitee_username: 相关用户名（用于备注）

        Returns:
            创建的积分批次对象
        """
        settings = SystemSettings.get_settings()

        if reward_type == 'inviter_register':
            amount = settings.referral_inviter_register_points
            source = PointsBalance.SOURCE_REFERRAL_INVITER_REGISTER
            note = f'邀请用户 {invitee_username} 注册奖励'
        elif reward_type == 'invitee_register':
            amount = settings.referral_invitee_register_points
            source = PointsBalance.SOURCE_REFERRAL_INVITEE_REGISTER
            note = f'受邀注册奖励'
        elif reward_type == 'inviter_upgrade':
            amount = settings.referral_inviter_upgrade_points
            source = PointsBalance.SOURCE_REFERRAL_INVITER_UPGRADE
            note = f'邀请用户 {invitee_username} 充值奖励'
        else:
            logger.warning(f"Unknown referral reward type: {reward_type}")
            return None

        if amount <= 0:
            return None

        return PointsService.grant_points(
            user_id=user_id,
            amount=amount,
            source=source,
            source_note=note,
            expire_days=settings.referral_points_expire_days
        )

    # ========== 积分消耗 ==========

    @staticmethod
    def consume_points(user_id: str, amount: int, description: str) -> Tuple[bool, str]:
        """
        消耗积分（FIFO策略，先过期先消耗）
        允许最后一次请求产生负积分

        Args:
            user_id: 用户ID
            amount: 消耗数量
            description: 描述

        Returns:
            (success: bool, message: str)
        """
        valid_points = PointsService.get_valid_points(user_id)

        # 如果已经是负数或0，拒绝消费
        if valid_points <= 0:
            return False, '积分不足，请充值后继续使用'

        # 允许消费（即使会产生负积分）
        now = datetime.now(timezone.utc)
        remaining_to_consume = amount

        # 获取所有有效批次，按过期时间排序（先过期的先消耗，NULL最后）
        balances = PointsBalance.query.filter(
            PointsBalance.user_id == user_id,
            PointsBalance.remaining > 0,
            or_(
                PointsBalance.expires_at.is_(None),
                PointsBalance.expires_at > now
            )
        ).order_by(
            # NULL排最后，其他按时间升序
            case((PointsBalance.expires_at.is_(None), 1), else_=0),
            PointsBalance.expires_at.asc()
        ).all()

        for balance in balances:
            if remaining_to_consume <= 0:
                break

            consume_from_this = min(balance.remaining, remaining_to_consume)
            balance.remaining -= consume_from_this
            remaining_to_consume -= consume_from_this

        # 如果还有剩余未消耗的（产生负积分情况）
        # 从最后一个批次继续扣（允许remaining为负）
        if remaining_to_consume > 0 and balances:
            last_balance = balances[-1]
            last_balance.remaining -= remaining_to_consume

        # 计算新的有效积分
        new_valid_points = PointsService.get_valid_points(user_id)

        # 记录流水
        transaction = PointsTransaction(
            user_id=user_id,
            type=PointsTransaction.TYPE_EXPENSE,
            amount=amount,
            balance_after=new_valid_points,
            description=description
        )
        db.session.add(transaction)

        logger.info(f"Consumed {amount} points from user {user_id}, remaining={new_valid_points}")

        return True, ''

    @staticmethod
    def can_consume(user_id: str, amount: int = 1) -> Tuple[bool, int, str]:
        """
        检查是否可以消耗积分

        Args:
            user_id: 用户ID
            amount: 预计消耗数量

        Returns:
            (can_consume: bool, remaining: int, message: str)
        """
        valid_points = PointsService.get_valid_points(user_id)

        if valid_points <= 0:
            return False, 0, '积分不足，请充值后继续使用'

        return True, valid_points, ''

    # ========== 管理员操作 ==========

    @staticmethod
    def admin_grant_points(
        user_id: str,
        amount: int,
        admin_id: str,
        note: Optional[str] = None,
        expire_days: Optional[int] = None
    ) -> PointsBalance:
        """
        管理员发放积分

        Args:
            user_id: 用户ID
            amount: 积分数量
            admin_id: 管理员ID
            note: 备注
            expire_days: 有效期天数

        Returns:
            创建的积分批次对象
        """
        return PointsService.grant_points(
            user_id=user_id,
            amount=amount,
            source=PointsBalance.SOURCE_ADMIN_GRANT,
            source_id=admin_id,
            source_note=note or '管理员发放',
            expire_days=expire_days
        )

    @staticmethod
    def admin_deduct_points(
        user_id: str,
        amount: int,
        admin_id: str,
        note: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        管理员扣除积分

        Args:
            user_id: 用户ID
            amount: 扣除数量
            admin_id: 管理员ID
            note: 备注

        Returns:
            (success: bool, message: str)
        """
        description = f'管理员扣除: {note or "无备注"}'
        return PointsService.consume_points(user_id, amount, description)

    # ========== 用户状态 ==========

    @staticmethod
    def get_user_points_status(user: User) -> dict:
        """
        获取用户积分状态

        Args:
            user: 用户对象

        Returns:
            积分状态字典
        """
        settings = SystemSettings.get_settings()
        valid_points = PointsService.get_valid_points(user.id)
        expiring = PointsService.get_expiring_points(user.id)

        can_generate_pages = valid_points // settings.points_per_page if settings.points_per_page > 0 else 0

        return {
            'valid_points': valid_points,
            'tier': 'premium' if valid_points > 0 or user.is_admin() else 'free',
            'is_admin': user.is_admin(),
            'expiring_soon': expiring,
            'points_per_page': settings.points_per_page,
            'can_generate_pages': can_generate_pages
        }


# ========== 便捷函数 ==========

def check_and_consume_points(user: User, pages_count: int = 1) -> Tuple[bool, str]:
    """
    检查并消耗积分（便捷函数）

    Args:
        user: 用户对象
        pages_count: 生成页数

    Returns:
        (success: bool, message: str)
    """
    # 管理员不消耗积分
    if user.is_admin():
        return True, ''

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

    return success, message
