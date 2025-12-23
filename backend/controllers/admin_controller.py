"""
Admin Controller - handles admin-only operations
"""
from flask import Blueprint, request
from models import db, User, RechargeCode, PremiumHistory
from utils import success_response, error_response, not_found, bad_request
from middleware import login_required, get_current_user
from datetime import datetime, timedelta
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def admin_required(f):
    """Admin role required decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = get_current_user()
        if not current_user or current_user.role != 'admin':
            return error_response('FORBIDDEN', '需要管理员权限', 403)
        return f(*args, **kwargs)
    return decorated_function


# ========== 用户管理 ==========

@admin_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def list_users():
    """
    GET /api/admin/users - 获取用户列表

    Query params:
    - page: 页码，默认 1
    - per_page: 每页数量，默认 20
    - search: 搜索用户名或邮箱
    - tier: 筛选用户等级 (free/premium)
    - role: 筛选角色 (user/admin)
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        tier = request.args.get('tier', '')
        role = request.args.get('role', '')

        query = User.query

        if search:
            query = query.filter(
                db.or_(
                    User.username.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%')
                )
            )

        if tier:
            query = query.filter_by(tier=tier)

        if role:
            query = query.filter_by(role=role)

        query = query.order_by(User.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return success_response({
            'users': [u.to_dict() for u in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
        })

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/users/<user_id>', methods=['GET'])
@login_required
@admin_required
def get_user(user_id):
    """
    GET /api/admin/users/{user_id} - 获取用户详情
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return not_found('User')

        return success_response(user.to_dict())

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/users/<user_id>/grant-premium', methods=['POST'])
@login_required
@admin_required
def grant_premium(user_id):
    """
    POST /api/admin/users/{user_id}/grant-premium - 给用户授予会员

    Body:
    {
        "duration_days": 30,
        "note": "可选备注"
    }
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return not_found('User')

        data = request.get_json() or {}
        duration_days = data.get('duration_days')
        note = data.get('note', '')

        if not duration_days or duration_days <= 0:
            return bad_request("duration_days 必须大于 0")

        current_admin = get_current_user()
        now = datetime.utcnow()

        # 计算新的到期时间
        if user.tier == 'premium' and user.premium_expires_at and user.premium_expires_at > now:
            new_expires_at = user.premium_expires_at + timedelta(days=duration_days)
        else:
            new_expires_at = now + timedelta(days=duration_days)

        # 更新用户
        user.tier = 'premium'
        user.premium_expires_at = new_expires_at
        user.updated_at = now

        # 记录历史
        history = PremiumHistory(
            user_id=user.id,
            action='admin_grant',
            duration_days=duration_days,
            admin_id=current_admin.id,
            note=note,
        )
        db.session.add(history)

        db.session.commit()

        return success_response({
            'message': f'已为用户 {user.username} 添加 {duration_days} 天会员',
            'user': user.to_dict(),
        })

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/users/<user_id>/revoke-premium', methods=['POST'])
@login_required
@admin_required
def revoke_premium(user_id):
    """
    POST /api/admin/users/{user_id}/revoke-premium - 撤销用户会员

    Body:
    {
        "note": "可选备注"
    }
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return not_found('User')

        if user.tier != 'premium':
            return bad_request("用户当前不是高级会员")

        data = request.get_json() or {}
        note = data.get('note', '')

        current_admin = get_current_user()
        now = datetime.utcnow()

        # 更新用户
        user.tier = 'free'
        user.premium_expires_at = None
        user.updated_at = now

        # 记录历史
        history = PremiumHistory(
            user_id=user.id,
            action='admin_revoke',
            admin_id=current_admin.id,
            note=note,
        )
        db.session.add(history)

        db.session.commit()

        return success_response({
            'message': f'已撤销用户 {user.username} 的会员资格',
            'user': user.to_dict(),
        })

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/users/<user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    """
    POST /api/admin/users/{user_id}/toggle-active - 启用/禁用用户
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return not_found('User')

        current_admin = get_current_user()
        if user.id == current_admin.id:
            return bad_request("不能禁用自己的账户")

        user.is_active = not user.is_active
        user.updated_at = datetime.utcnow()
        db.session.commit()

        status = "启用" if user.is_active else "禁用"
        return success_response({
            'message': f'已{status}用户 {user.username}',
            'user': user.to_dict(),
        })

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


# ========== 充值码管理 ==========

@admin_bp.route('/recharge-codes', methods=['GET'])
@login_required
@admin_required
def list_recharge_codes():
    """
    GET /api/admin/recharge-codes - 获取充值码列表

    Query params:
    - page: 页码
    - per_page: 每页数量
    - is_used: 筛选是否已使用 (true/false)
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        is_used = request.args.get('is_used', '')

        query = RechargeCode.query

        if is_used == 'true':
            query = query.filter_by(is_used=True)
        elif is_used == 'false':
            query = query.filter_by(is_used=False)

        query = query.order_by(RechargeCode.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return success_response({
            'codes': [c.to_dict() for c in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
        })

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/recharge-codes', methods=['POST'])
@login_required
@admin_required
def create_recharge_codes():
    """
    POST /api/admin/recharge-codes - 批量生成充值码

    Body:
    {
        "count": 10,
        "duration_days": 30,
        "expires_in_days": 365  // 可选，充值码有效期
    }
    """
    try:
        data = request.get_json() or {}
        count = data.get('count', 1)
        duration_days = data.get('duration_days')
        expires_in_days = data.get('expires_in_days')

        if not duration_days or duration_days <= 0:
            return bad_request("duration_days 必须大于 0")

        if count <= 0 or count > 100:
            return bad_request("count 必须在 1-100 之间")

        current_admin = get_current_user()
        now = datetime.utcnow()
        expires_at = now + timedelta(days=expires_in_days) if expires_in_days else None

        codes = []
        for _ in range(count):
            code = RechargeCode(
                code=RechargeCode.generate_code(),
                duration_days=duration_days,
                created_by_admin_id=current_admin.id,
                expires_at=expires_at,
            )
            db.session.add(code)
            codes.append(code)

        db.session.commit()

        return success_response({
            'message': f'已生成 {count} 个充值码',
            'codes': [c.to_dict() for c in codes],
        })

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/recharge-codes/<code_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_recharge_code(code_id):
    """
    DELETE /api/admin/recharge-codes/{code_id} - 删除充值码（仅未使用的）
    """
    try:
        code = RechargeCode.query.get(code_id)
        if not code:
            return not_found('RechargeCode')

        if code.is_used:
            return bad_request("已使用的充值码不能删除")

        db.session.delete(code)
        db.session.commit()

        return success_response({'message': '充值码已删除'})

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


# ========== 统计信息 ==========

@admin_bp.route('/stats', methods=['GET'])
@login_required
@admin_required
def get_admin_stats():
    """
    GET /api/admin/stats - 获取系统统计信息
    """
    try:
        total_users = User.query.count()
        premium_users = User.query.filter_by(tier='premium').count()
        active_users = User.query.filter_by(is_active=True).count()

        total_codes = RechargeCode.query.count()
        used_codes = RechargeCode.query.filter_by(is_used=True).count()
        unused_codes = total_codes - used_codes

        return success_response({
            'users': {
                'total': total_users,
                'premium': premium_users,
                'free': total_users - premium_users,
                'active': active_users,
            },
            'recharge_codes': {
                'total': total_codes,
                'used': used_codes,
                'unused': unused_codes,
            },
        })

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)
