"""
Admin Controller - handles admin-only operations (积分版)
"""
from flask import Blueprint, request
from models import db, User, RechargeCode, PremiumHistory, SystemSettings, Referral, DailyUsage, PointsBalance, PointsTransaction
from utils import success_response, error_response, not_found, bad_request
from middleware import login_required, get_current_user
from datetime import datetime, timezone, timedelta, date
from functools import wraps
from services.points_service import PointsService

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
    POST /api/admin/users/{user_id}/grant-premium - 给用户发放积分

    Body:
    {
        "points": 500,              // 积分数量
        "expire_days": null,        // 有效期天数，null表示永不过期
        "note": "可选备注"
    }

    兼容旧参数（会自动转换）:
    {
        "duration_days": 30         // 会按 1天=200积分 转换
    }
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return not_found('User')

        data = request.get_json() or {}
        points = data.get('points')
        expire_days = data.get('expire_days')
        note = data.get('note', '')

        # 兼容旧参数
        if not points and data.get('duration_days'):
            points = data.get('duration_days') * 200  # 1天=200积分
            expire_days = 30  # 默认30天有效期

        if not points or points <= 0:
            return bad_request("points 必须大于 0")

        current_admin = get_current_user()

        # 发放积分
        balance = PointsService.admin_grant_points(
            user_id=user.id,
            amount=points,
            admin_id=current_admin.id,
            note=note or '管理员发放',
            expire_days=expire_days
        )

        db.session.commit()

        return success_response({
            'message': f'已为用户 {user.username} 发放 {points} 积分',
            'points_added': points,
            'expires_at': balance.expires_at.isoformat() if balance.expires_at else None,
            'user': user.to_dict(),
        })

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/users/<user_id>/grant-points', methods=['POST'])
@login_required
@admin_required
def grant_points(user_id):
    """
    POST /api/admin/users/{user_id}/grant-points - 给用户发放积分（新接口）

    Body:
    {
        "points": 500,
        "expire_days": null,
        "note": "可选备注"
    }
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return not_found('User')

        data = request.get_json() or {}
        points = data.get('points')
        expire_days = data.get('expire_days')
        note = data.get('note', '')

        if not points or points <= 0:
            return bad_request("points 必须大于 0")

        current_admin = get_current_user()

        balance = PointsService.admin_grant_points(
            user_id=user.id,
            amount=points,
            admin_id=current_admin.id,
            note=note or '管理员发放',
            expire_days=expire_days
        )

        db.session.commit()

        return success_response({
            'message': f'已为用户 {user.username} 发放 {points} 积分',
            'points_added': points,
            'expires_at': balance.expires_at.isoformat() if balance.expires_at else None,
            'new_balance': PointsService.get_valid_points(user.id),
            'user': user.to_dict(),
        })

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/users/<user_id>/deduct-points', methods=['POST'])
@login_required
@admin_required
def deduct_points(user_id):
    """
    POST /api/admin/users/{user_id}/deduct-points - 扣除用户积分

    Body:
    {
        "points": 100,
        "note": "扣除原因"
    }
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return not_found('User')

        data = request.get_json() or {}
        points = data.get('points')
        note = data.get('note', '')

        if not points or points <= 0:
            return bad_request("points 必须大于 0")

        current_admin = get_current_user()

        success, message = PointsService.admin_deduct_points(
            user_id=user.id,
            amount=points,
            admin_id=current_admin.id,
            note=note
        )

        if not success:
            return bad_request(message)

        db.session.commit()

        return success_response({
            'message': f'已扣除用户 {user.username} 的 {points} 积分',
            'points_deducted': points,
            'new_balance': PointsService.get_valid_points(user.id),
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
    POST /api/admin/users/{user_id}/revoke-premium - 清空用户积分（相当于撤销会员）

    Body:
    {
        "note": "可选备注"
    }
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return not_found('User')

        valid_points = PointsService.get_valid_points(user.id)
        if valid_points <= 0:
            return bad_request("用户当前没有积分")

        data = request.get_json() or {}
        note = data.get('note', '')

        current_admin = get_current_user()

        # 扣除所有积分
        success, message = PointsService.admin_deduct_points(
            user_id=user.id,
            amount=valid_points,
            admin_id=current_admin.id,
            note=note or '管理员清空积分'
        )

        db.session.commit()

        return success_response({
            'message': f'已清空用户 {user.username} 的 {valid_points} 积分',
            'points_deducted': valid_points,
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


@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """
    DELETE /api/admin/users/{user_id} - 删除用户

    注意：
    - 不能删除管理员账户
    - 不能删除自己
    - 会级联删除用户的所有数据（项目、使用记录等）
    """
    try:
        from models import PremiumHistory, RechargeCode, UserSettings, Referral

        user = User.query.get(user_id)
        if not user:
            return not_found('User')

        current_admin = get_current_user()

        # 不能删除自己
        if user.id == current_admin.id:
            return bad_request("不能删除自己的账户")

        # 不能删除管理员
        if user.role == 'admin':
            return bad_request("不能删除管理员账户")

        username = user.username

        # 手动删除关联数据（避免外键约束问题）
        # 1. 删除会员历史记录
        PremiumHistory.query.filter_by(user_id=user_id).delete()
        # 2. 清除充值码的使用者关联（不删除充值码本身）
        RechargeCode.query.filter_by(used_by_user_id=user_id).update({'used_by_user_id': None})
        # 3. 删除用户设置
        UserSettings.query.filter_by(user_id=user_id).delete()
        # 4. 删除使用记录
        DailyUsage.query.filter_by(user_id=user_id).delete()
        # 5. 删除邀请记录（作为邀请者或被邀请者）
        Referral.query.filter_by(inviter_user_id=user_id).delete()
        Referral.query.filter_by(invitee_user_id=user_id).delete()

        # 删除用户
        db.session.delete(user)
        db.session.commit()

        return success_response({
            'message': f'已删除用户 {username}',
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
    POST /api/admin/recharge-codes - 批量生成充值码（积分版）

    Body:
    {
        "count": 10,
        "points": 500,              // 积分数量
        "points_expire_days": null, // 积分有效期天数，null表示永不过期
        "expires_in_days": 365      // 可选，充值码本身的有效期
    }
    """
    try:
        data = request.get_json() or {}
        count = data.get('count', 1)
        points = data.get('points')
        points_expire_days = data.get('points_expire_days')  # null表示永不过期
        expires_in_days = data.get('expires_in_days')

        if not points or points <= 0:
            return bad_request("points 必须大于 0")

        if count <= 0 or count > 100:
            return bad_request("count 必须在 1-100 之间")

        current_admin = get_current_user()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=expires_in_days) if expires_in_days else None

        codes = []
        for _ in range(count):
            code = RechargeCode(
                code=RechargeCode.generate_code(),
                points=points,
                points_expire_days=points_expire_days,
                created_by_admin_id=current_admin.id,
                expires_at=expires_at,
            )
            db.session.add(code)
            codes.append(code)

        db.session.commit()

        return success_response({
            'message': f'已生成 {count} 个充值码（每个 {points} 积分）',
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


# ========== 系统设置管理 ==========

@admin_bp.route('/system-settings', methods=['GET'])
@login_required
@admin_required
def get_system_settings():
    """
    GET /api/admin/system-settings - 获取系统设置
    """
    try:
        settings = SystemSettings.get_settings()
        return success_response(settings.to_dict())
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/system-settings', methods=['PUT'])
@login_required
@admin_required
def update_system_settings():
    """
    PUT /api/admin/system-settings - 更新系统设置

    Body (所有字段可选):
    {
        // 注册设置
        "default_user_tier": "free",
        "default_premium_days": 30,
        "require_email_verification": true,

        // 积分设置
        "points_per_page": 15,
        "register_bonus_points": 300,
        "register_bonus_expire_days": 3,

        // 裂变积分设置
        "referral_inviter_register_points": 100,
        "referral_invitee_register_points": 100,
        "referral_inviter_upgrade_points": 450,
        "referral_points_expire_days": 30,
        "referral_domain": "ppt.netopstec.com",

        // 用量限制（旧版，保留兼容）
        "daily_image_generation_limit": 20,
        "enable_usage_limit": true,

        // SMTP设置
        "smtp_host": "smtp.example.com",
        "smtp_port": 465,
        "smtp_user": "user@example.com",
        "smtp_password": "password",
        "smtp_use_ssl": true,
        "smtp_sender_name": "Banana Slides"
    }
    """
    try:
        settings = SystemSettings.get_settings()
        data = request.get_json() or {}

        # 注册设置
        if 'default_user_tier' in data:
            if data['default_user_tier'] not in ['free', 'premium']:
                return bad_request("default_user_tier 必须是 'free' 或 'premium'")
            settings.default_user_tier = data['default_user_tier']

        if 'default_premium_days' in data:
            settings.default_premium_days = int(data['default_premium_days'])

        if 'require_email_verification' in data:
            settings.require_email_verification = bool(data['require_email_verification'])

        # 积分设置
        if 'points_per_page' in data:
            settings.points_per_page = int(data['points_per_page'])

        if 'register_bonus_points' in data:
            settings.register_bonus_points = int(data['register_bonus_points'])

        if 'register_bonus_expire_days' in data:
            val = data['register_bonus_expire_days']
            settings.register_bonus_expire_days = int(val) if val is not None else None

        # 裂变积分设置
        if 'referral_enabled' in data:
            settings.referral_enabled = bool(data['referral_enabled'])

        if 'referral_inviter_register_points' in data:
            settings.referral_inviter_register_points = int(data['referral_inviter_register_points'])

        if 'referral_invitee_register_points' in data:
            settings.referral_invitee_register_points = int(data['referral_invitee_register_points'])

        if 'referral_inviter_upgrade_points' in data:
            settings.referral_inviter_upgrade_points = int(data['referral_inviter_upgrade_points'])

        if 'referral_points_expire_days' in data:
            val = data['referral_points_expire_days']
            settings.referral_points_expire_days = int(val) if val is not None else None

        # 旧版裂变设置（保留兼容）
        if 'referral_register_reward_days' in data:
            settings.referral_register_reward_days = int(data['referral_register_reward_days'])

        if 'referral_invitee_reward_days' in data:
            settings.referral_invitee_reward_days = int(data['referral_invitee_reward_days'])

        if 'referral_premium_reward_days' in data:
            settings.referral_premium_reward_days = int(data['referral_premium_reward_days'])

        if 'referral_domain' in data:
            settings.referral_domain = data['referral_domain'].strip()

        # 用量限制（旧版，保留兼容）
        if 'daily_image_generation_limit' in data:
            settings.daily_image_generation_limit = int(data['daily_image_generation_limit'])

        if 'enable_usage_limit' in data:
            settings.enable_usage_limit = bool(data['enable_usage_limit'])

        # SMTP设置
        if 'smtp_host' in data:
            settings.smtp_host = data['smtp_host'].strip() if data['smtp_host'] else None

        if 'smtp_port' in data:
            settings.smtp_port = int(data['smtp_port']) if data['smtp_port'] else 465

        if 'smtp_user' in data:
            settings.smtp_user = data['smtp_user'].strip() if data['smtp_user'] else None

        if 'smtp_password' in data:
            # 前端占位符约定“留空则不修改”，因此空字符串不覆盖已有密码；
            # 如需清空密码，可显式传 null。
            if data['smtp_password'] is None:
                settings.smtp_password = None
            elif isinstance(data['smtp_password'], str) and data['smtp_password'] != '':
                settings.smtp_password = data['smtp_password']

        if 'smtp_use_ssl' in data:
            settings.smtp_use_ssl = bool(data['smtp_use_ssl'])

        if 'smtp_sender_name' in data:
            settings.smtp_sender_name = data['smtp_sender_name'].strip() if data['smtp_sender_name'] else 'Banana Slides'

        db.session.commit()

        return success_response({
            'message': '设置已更新',
            'settings': settings.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/system-settings/test-smtp', methods=['POST'])
@login_required
@admin_required
def test_smtp():
    """
    POST /api/admin/system-settings/test-smtp - 测试SMTP配置

    Body:
    {
        "test_email": "test@example.com"  // 发送测试邮件的目标地址
    }
    """
    try:
        data = request.get_json() or {}
        test_email = data.get('test_email', '').strip()

        if not test_email:
            return bad_request("请提供测试邮箱地址")

        from services.email_service import get_email_service

        email_service = get_email_service()

        # 发送测试邮件
        success, message = email_service.send_email(
            to_email=test_email,
            subject='【Banana Slides】SMTP配置测试',
            html_content='''
            <div style="font-family: sans-serif; padding: 20px;">
                <h2>🍌 SMTP配置测试成功！</h2>
                <p>如果您收到这封邮件，说明SMTP配置正确。</p>
                <p style="color: #666; font-size: 12px;">此邮件由系统自动发送，请勿回复。</p>
            </div>
            ''',
            text_content='SMTP配置测试成功！如果您收到这封邮件，说明SMTP配置正确。'
        )

        if success:
            return success_response({'message': f'测试邮件已发送至 {test_email}'})

        # SMTP 配置/连接类错误属于客户端配置问题，返回 400 方便前端展示具体原因
        return error_response('SMTP_ERROR', message, 400)

    except ValueError as e:
        return error_response('CONFIG_ERROR', str(e), 400)
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


# ========== 邀请裂变统计 ==========

@admin_bp.route('/referral/stats', methods=['GET'])
@login_required
@admin_required
def get_referral_stats():
    """
    GET /api/admin/referral/stats - 获取邀请裂变统计
    """
    try:
        total_referrals = Referral.query.count()
        registered_referrals = Referral.query.filter(
            Referral.status.in_(['registered', 'premium'])
        ).count()
        premium_referrals = Referral.query.filter_by(status='premium').count()

        # 计算总奖励（积分体系下：这里统计的是积分；字段名保持兼容）
        total_register_rewards = db.session.query(
            db.func.sum(Referral.register_reward_days)
        ).filter(Referral.register_reward_granted == True).scalar() or 0

        total_premium_rewards = db.session.query(
            db.func.sum(Referral.premium_reward_days)
        ).filter(Referral.premium_reward_granted == True).scalar() or 0

        total_rewards = total_register_rewards + total_premium_rewards

        return success_response({
            'total_referrals': total_referrals,
            'registered_referrals': registered_referrals,
            'premium_referrals': premium_referrals,
            # 新字段：明确为积分
            'total_register_rewards_points': total_register_rewards,
            'total_premium_rewards_points': total_premium_rewards,
            'total_rewards_points': total_rewards,
            # 兼容旧字段名（仍返回，但语义已是积分）
            'total_register_rewards_days': total_register_rewards,
            'total_premium_rewards_days': total_premium_rewards,
            'total_rewards_days': total_rewards,
        })

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/referral/list', methods=['GET'])
@login_required
@admin_required
def get_all_referrals():
    """
    GET /api/admin/referral/list - 获取所有邀请记录

    Query params:
    - page: 页码
    - per_page: 每页数量
    - status: 筛选状态 (pending/registered/premium)
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', '')

        query = Referral.query

        if status:
            query = query.filter_by(status=status)

        query = query.order_by(Referral.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        referrals = []
        for ref in pagination.items:
            inviter = User.query.get(ref.inviter_user_id)
            invitee = User.query.get(ref.invitee_user_id) if ref.invitee_user_id else None
            referrals.append({
                'id': ref.id,
                'inviter_username': inviter.username if inviter else None,
                'invitee_username': invitee.username if invitee else None,
                'invitee_email': ref.invitee_email,
                'status': ref.status,
                'register_reward_granted': ref.register_reward_granted,
                'register_reward_days': ref.register_reward_days,
                'premium_reward_granted': ref.premium_reward_granted,
                'premium_reward_days': ref.premium_reward_days,
                'created_at': ref.created_at.isoformat() if ref.created_at else None,
            })

        return success_response({
            'referrals': referrals,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
        })

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


# ========== 用量统计 ==========

@admin_bp.route('/usage/stats', methods=['GET'])
@login_required
@admin_required
def get_usage_stats():
    """
    GET /api/admin/usage/stats - 获取用量统计

    Query params:
    - days: 统计最近多少天，默认7天
    """
    try:
        days = request.args.get('days', 7, type=int)
        today = date.today()
        start_date = today - timedelta(days=days - 1)

        # 按天统计
        daily_stats = []
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            usage_count = db.session.query(
                db.func.sum(DailyUsage.image_generation_count)
            ).filter(DailyUsage.usage_date == current_date).scalar() or 0

            user_count = DailyUsage.query.filter_by(usage_date=current_date).count()

            daily_stats.append({
                'date': current_date.isoformat(),
                'image_count': usage_count,
                'user_count': user_count,
            })

        # 总计
        total_today = db.session.query(
            db.func.sum(DailyUsage.image_generation_count)
        ).filter(DailyUsage.usage_date == today).scalar() or 0

        total_all = db.session.query(
            db.func.sum(DailyUsage.image_generation_count)
        ).scalar() or 0

        return success_response({
            'daily_stats': daily_stats,
            'today_total': total_today,
            'all_time_total': total_all,
        })

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@admin_bp.route('/usage/user-stats', methods=['GET'])
@login_required
@admin_required
def get_user_usage_stats():
    """
    GET /api/admin/usage/user-stats - 获取每个用户的使用量统计

    只统计使用系统API的调用数据（用户自己的API调用不计入）

    费用计算规则：
    - 图像生成：1.5元/次
    - 文本调用：3.5元/1M tokens

    Returns:
    {
        "user_stats": [
            {
                "user_id": "...",
                "username": "...",
                "email": "...",
                "tier": "free|premium",
                "image_generation_count": 100,
                "text_generation_count": 50,
                "total_tokens": 500000,
                "image_cost": 150.0,
                "text_cost": 1.75,
                "total_cost": 151.75
            }
        ],
        "summary": {
            "total_image_count": 1000,
            "total_text_count": 500,
            "total_tokens": 5000000,
            "total_image_cost": 1500.0,
            "total_text_cost": 17.5,
            "total_cost": 1517.5
        }
    }
    """
    try:
        # 定价常量
        IMAGE_COST_PER_CALL = 1.5  # 元/次
        TEXT_COST_PER_MILLION_TOKENS = 3.5  # 元/1M tokens

        # 按用户汇总使用量（只统计使用系统API的记录）
        user_usage = db.session.query(
            DailyUsage.user_id,
            db.func.sum(DailyUsage.image_generation_count).label('image_count'),
            db.func.sum(DailyUsage.text_generation_count).label('text_count'),
            db.func.sum(DailyUsage.total_tokens).label('tokens')
        ).filter(
            DailyUsage.used_system_api == True
        ).group_by(DailyUsage.user_id).all()

        # 获取用户信息
        user_stats = []
        total_image_count = 0
        total_text_count = 0
        total_tokens = 0

        for usage in user_usage:
            user = User.query.get(usage.user_id)
            if not user:
                continue

            # 转换为 int（MySQL 可能返回 Decimal 类型）
            image_count = int(usage.image_count or 0)
            text_count = int(usage.text_count or 0)
            tokens = int(usage.tokens or 0)

            # 计算费用
            image_cost = image_count * IMAGE_COST_PER_CALL
            text_cost = (tokens / 1_000_000) * TEXT_COST_PER_MILLION_TOKENS

            user_stats.append({
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'tier': user.get_effective_tier(),  # 实际有效的会员等级
                'stored_tier': user.tier,  # 数据库存储的原始等级
                'image_generation_count': image_count,
                'text_generation_count': text_count,
                'total_tokens': tokens,
                'image_cost': round(image_cost, 2),
                'text_cost': round(text_cost, 2),
                'total_cost': round(image_cost + text_cost, 2),
            })

            total_image_count += image_count
            total_text_count += text_count
            total_tokens += tokens

        # 按总消费降序排序
        user_stats.sort(key=lambda x: x['total_cost'], reverse=True)

        # 计算汇总
        total_image_cost = total_image_count * IMAGE_COST_PER_CALL
        total_text_cost = (total_tokens / 1_000_000) * TEXT_COST_PER_MILLION_TOKENS

        return success_response({
            'user_stats': user_stats,
            'summary': {
                'total_image_count': total_image_count,
                'total_text_count': total_text_count,
                'total_tokens': total_tokens,
                'total_image_cost': round(total_image_cost, 2),
                'total_text_cost': round(total_text_cost, 2),
                'total_cost': round(total_image_cost + total_text_cost, 2),
            }
        })

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)
