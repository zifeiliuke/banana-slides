"""
Premium Controller - handles premium membership and points (积分版)
"""
from flask import Blueprint, request
from models import db, User, RechargeCode, PointsBalance, PointsTransaction
from utils import success_response, error_response, not_found, bad_request
from middleware import login_required, get_current_user
from datetime import datetime, timezone
from services.referral_service import ReferralService
from services.points_service import PointsService

premium_bp = Blueprint('premium', __name__, url_prefix='/api/premium')


@premium_bp.route('/status', methods=['GET'])
@login_required
def get_premium_status():
    """
    GET /api/premium/status - 获取当前用户的会员状态（积分版）
    """
    try:
        current_user = get_current_user()
        status = PointsService.get_user_points_status(current_user)

        return success_response(status)

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@premium_bp.route('/history', methods=['GET'])
@login_required
def get_premium_history():
    """
    GET /api/premium/history - 获取用户的积分流水记录
    """
    try:
        current_user = get_current_user()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        type_filter = request.args.get('type', None)

        result = PointsService.get_transactions(
            current_user.id,
            type_filter=type_filter,
            page=page,
            per_page=per_page
        )

        return success_response(result)

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@premium_bp.route('/balances', methods=['GET'])
@login_required
def get_points_balances():
    """
    GET /api/premium/balances - 获取用户的积分批次明细
    """
    try:
        current_user = get_current_user()
        include_expired = request.args.get('include_expired', 'false').lower() == 'true'

        balances = PointsService.get_points_balances(current_user.id, include_expired)

        return success_response({
            'balances': [b.to_dict() for b in balances]
        })

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@premium_bp.route('/redeem', methods=['POST'])
@login_required
def redeem_code():
    """
    POST /api/premium/redeem - 兑换充值码（积分版）

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

        if recharge_code.expires_at:
            now = datetime.now(timezone.utc)
            expires_at = recharge_code.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                return bad_request("该充值码已过期")

        # 检查积分数量
        if recharge_code.points <= 0:
            return bad_request("该充值码无效（积分为0）")

        # 更新充值码状态
        now = datetime.now(timezone.utc)
        recharge_code.is_used = True
        recharge_code.used_by_user_id = current_user.id
        recharge_code.used_at = now

        # 发放积分
        balance = PointsService.grant_points(
            user_id=current_user.id,
            amount=recharge_code.points,
            source=PointsBalance.SOURCE_RECHARGE,
            source_id=recharge_code.id,
            source_note=f'充值码兑换: {code_str}',
            expire_days=recharge_code.points_expire_days
        )

        db.session.commit()

        # 处理邀请升级奖励（首次充值给邀请者发放奖励）
        try:
            ReferralService.process_premium_upgrade_referral(current_user)
        except Exception as e:
            # 邀请奖励处理失败不影响主流程
            import logging
            logging.warning(f"Failed to process premium upgrade referral: {e}")

        # 获取最新积分状态
        new_valid_points = PointsService.get_valid_points(current_user.id)

        return success_response({
            'message': f'充值成功！已增加 {recharge_code.points} 积分',
            'points_added': recharge_code.points,
            'expires_at': balance.expires_at.isoformat() if balance.expires_at else None,
            'new_balance': new_valid_points,
            'tier': current_user.get_effective_tier(),
            'is_premium_active': current_user.is_premium_active(),
        })

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


# ========== 积分相关接口（新增） ==========

@premium_bp.route('/points/balance', methods=['GET'])
@login_required
def get_points_balance():
    """
    GET /api/premium/points/balance - 获取用户积分余额
    """
    try:
        current_user = get_current_user()
        status = PointsService.get_user_points_status(current_user)

        return success_response(status)

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@premium_bp.route('/points/transactions', methods=['GET'])
@login_required
def get_points_transactions():
    """
    GET /api/premium/points/transactions - 获取积分流水
    """
    try:
        current_user = get_current_user()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        type_filter = request.args.get('type', None)

        result = PointsService.get_transactions(
            current_user.id,
            type_filter=type_filter,
            page=page,
            per_page=per_page
        )

        return success_response(result)

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)
