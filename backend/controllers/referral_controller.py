"""
Referral Controller - handles referral/invitation related endpoints
"""
from flask import Blueprint, request
from models import db
from utils import success_response, error_response
from middleware import login_required, get_current_user
from services.referral_service import ReferralService
from services.usage_service import UsageService

referral_bp = Blueprint('referral', __name__, url_prefix='/api/referral')


@referral_bp.route('/stats', methods=['GET'])
@login_required
def get_referral_stats():
    """
    GET /api/referral/stats - 获取当前用户的邀请统计
    """
    try:
        current_user = get_current_user()
        stats = ReferralService.get_user_referral_stats(current_user)
        return success_response(stats)
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@referral_bp.route('/list', methods=['GET'])
@login_required
def get_referral_list():
    """
    GET /api/referral/list - 获取当前用户的邀请列表

    Query params:
    - page: 页码，默认 1
    - per_page: 每页数量，默认 20
    """
    try:
        current_user = get_current_user()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        result = ReferralService.get_user_referral_list(current_user, page, per_page)
        return success_response(result)
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@referral_bp.route('/code', methods=['GET'])
@login_required
def get_referral_code():
    """
    GET /api/referral/code - 获取当前用户的邀请码
    """
    try:
        current_user = get_current_user()

        # 确保用户有邀请码
        if not current_user.referral_code:
            current_user.ensure_referral_code()
            db.session.commit()

        from models import SystemSettings
        settings = SystemSettings.get_settings()

        return success_response({
            'referral_code': current_user.referral_code,
            'referral_link': f'https://{settings.referral_domain}/register?ref={current_user.referral_code}',
        })
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


# ========== 用量查询接口 ==========

usage_bp = Blueprint('usage', __name__, url_prefix='/api/usage')


@usage_bp.route('/today', methods=['GET'])
@login_required
def get_today_usage():
    """
    GET /api/usage/today - 获取当前用户今日的用量状态
    """
    try:
        current_user = get_current_user()
        status = UsageService.get_user_usage_status(current_user)
        return success_response(status)
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)
