"""
Points Controller - 积分相关API接口
"""
from flask import Blueprint, request
from models import db, SystemSettings
from utils import success_response, error_response
from middleware import login_required, get_current_user
from services.points_service import PointsService

points_bp = Blueprint('points', __name__, url_prefix='/api/points')


@points_bp.route('/balance', methods=['GET'])
@login_required
def get_balance():
    """
    GET /api/points/balance - 获取用户积分余额

    Response:
    {
        "valid_points": 850,
        "tier": "premium",
        "is_admin": false,
        "expiring_soon": {
            "points": 100,
            "days": 7,
            "earliest_expire": "2025-01-20T00:00:00Z"
        },
        "points_per_page": 15,
        "can_generate_pages": 56
    }
    """
    try:
        current_user = get_current_user()
        status = PointsService.get_user_points_status(current_user)
        return success_response(status)
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@points_bp.route('/transactions', methods=['GET'])
@login_required
def get_transactions():
    """
    GET /api/points/transactions - 获取积分流水记录

    Query params:
    - page: 页码（默认1）
    - per_page: 每页数量（默认20）
    - type: 筛选类型（income/expense/expired）

    Response:
    {
        "transactions": [...],
        "total": 100,
        "page": 1,
        "per_page": 20
    }
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


@points_bp.route('/balances', methods=['GET'])
@login_required
def get_balances():
    """
    GET /api/points/balances - 获取积分批次明细

    Query params:
    - include_expired: 是否包含已过期批次（默认false）

    Response:
    {
        "balances": [
            {
                "id": "xxx",
                "amount": 300,
                "remaining": 150,
                "source": "register",
                "expires_at": "2025-01-15T00:00:00Z",
                "is_expired": false,
                "is_expiring_soon": true,
                "created_at": "2025-01-12T00:00:00Z"
            }
        ]
    }
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


@points_bp.route('/config', methods=['GET'])
@login_required
def get_points_config():
    """
    GET /api/points/config - 获取积分配置（公开部分）

    Response:
    {
        "points_per_page": 15,
        "register_bonus_points": 300,
        "register_bonus_expire_days": 3,
        "referral_inviter_register_points": 100,
        "referral_invitee_register_points": 100,
        "referral_inviter_upgrade_points": 450
    }
    """
    try:
        settings = SystemSettings.get_settings()

        return success_response({
            'points_per_page': settings.points_per_page,
            'register_bonus_points': settings.register_bonus_points,
            'register_bonus_expire_days': settings.register_bonus_expire_days,
            'referral_inviter_register_points': settings.referral_inviter_register_points,
            'referral_invitee_register_points': settings.referral_invitee_register_points,
            'referral_inviter_upgrade_points': settings.referral_inviter_upgrade_points,
        })
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)
