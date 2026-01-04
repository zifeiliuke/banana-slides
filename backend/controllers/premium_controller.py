"""
Premium Controller - handles premium membership and recharge
"""
from flask import Blueprint, request
from models import db, User, RechargeCode, PremiumHistory
from utils import success_response, error_response, not_found, bad_request
from middleware import login_required, get_current_user
from datetime import datetime, timedelta
from services.referral_service import ReferralService

premium_bp = Blueprint('premium', __name__, url_prefix='/api/premium')


@premium_bp.route('/status', methods=['GET'])
@login_required
def get_premium_status():
    """
    GET /api/premium/status - 获取当前用户的会员状态
    """
    try:
        current_user = get_current_user()

        return success_response({
            'tier': current_user.get_effective_tier(),  # 实际有效的会员等级
            'stored_tier': current_user.tier,  # 数据库存储的原始等级
            'is_premium_active': current_user.is_premium_active(),
            'premium_expires_at': current_user.premium_expires_at.isoformat() if current_user.premium_expires_at else None,
        })

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@premium_bp.route('/history', methods=['GET'])
@login_required
def get_premium_history():
    """
    GET /api/premium/history - 获取用户的会员历史记录
    """
    try:
        current_user = get_current_user()

        history = PremiumHistory.query.filter_by(user_id=current_user.id) \
            .order_by(PremiumHistory.created_at.desc()) \
            .limit(50) \
            .all()

        return success_response({
            'history': [h.to_dict() for h in history]
        })

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@premium_bp.route('/redeem', methods=['POST'])
@login_required
def redeem_code():
    """
    POST /api/premium/redeem - 兑换充值码

    Body:
    {
        "code": "ABCD1234EFGH5678"
    }
    """
    try:
        current_user = get_current_user()
        data = request.get_json() or {}
        code_str = data.get('code', '').strip().upper()

        if not code_str:
            return bad_request("请输入充值码")

        # 查找充值码
        recharge_code = RechargeCode.query.filter_by(code=code_str).first()

        if not recharge_code:
            return bad_request("无效的充值码")

        if recharge_code.is_used:
            return bad_request("该充值码已被使用")

        if recharge_code.expires_at and recharge_code.expires_at < datetime.utcnow():
            return bad_request("该充值码已过期")

        # 计算新的到期时间
        now = datetime.utcnow()
        if current_user.tier == 'premium' and current_user.premium_expires_at and current_user.premium_expires_at > now:
            # 已有会员，在现有基础上延长
            new_expires_at = current_user.premium_expires_at + timedelta(days=recharge_code.duration_days)
        else:
            # 新开通会员
            new_expires_at = now + timedelta(days=recharge_code.duration_days)

        # 更新充值码状态
        recharge_code.is_used = True
        recharge_code.used_by_user_id = current_user.id
        recharge_code.used_at = now

        # 更新用户会员状态
        current_user.tier = 'premium'
        current_user.premium_expires_at = new_expires_at
        current_user.updated_at = now

        # 记录历史
        history = PremiumHistory(
            user_id=current_user.id,
            action='recharge',
            duration_days=recharge_code.duration_days,
            recharge_code_id=recharge_code.id,
        )
        db.session.add(history)

        db.session.commit()

        # 处理邀请升级奖励（给邀请者发放奖励）
        try:
            ReferralService.process_premium_upgrade_referral(current_user)
        except Exception as e:
            # 邀请奖励处理失败不影响主流程
            import logging
            logging.warning(f"Failed to process premium upgrade referral: {e}")

        return success_response({
            'message': f'充值成功！已增加 {recharge_code.duration_days} 天会员时长',
            'tier': current_user.get_effective_tier(),  # 实际有效的会员等级
            'stored_tier': current_user.tier,  # 数据库存储的原始等级
            'is_premium_active': True,
            'premium_expires_at': new_expires_at.isoformat(),
            'duration_days': recharge_code.duration_days,
        })

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)
