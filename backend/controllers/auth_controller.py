"""
Authentication Controller - handles user registration, login, logout
"""
import re
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify

from models import db, User, EmailVerification, SystemSettings
from middleware import (
    login_required,
    get_current_user,
    generate_access_token,
    generate_refresh_token,
    decode_token,
    AuthenticationError,
)
from services.referral_service import ReferralService
from services.points_service import PointsService

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def is_valid_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


@auth_bp.route('/send-verification', methods=['POST'])
def send_verification_code():
    """
    POST /api/auth/send-verification - 发送邮箱验证码

    Request body:
    {
        "email": "user@example.com"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': '邮箱地址不能为空'}), 400

    if not is_valid_email(email):
        return jsonify({'error': '邮箱格式不正确'}), 400

    # 检查邮箱是否已注册
    if User.query.filter_by(email=email).first():
        return jsonify({'error': '该邮箱已被注册'}), 409

    # 检查发送频率
    can_send, wait_seconds = EmailVerification.can_send_new_code(email)
    if not can_send:
        return jsonify({'error': f'请等待 {wait_seconds} 秒后再试'}), 429

    # 创建验证码
    verification = EmailVerification.create_verification(email)

    # 发送邮件
    try:
        from services.email_service import get_email_service
        email_service = get_email_service()
        success, message = email_service.send_verification_code(email, verification.code)

        if not success:
            return jsonify({'error': message}), 500

        return jsonify({
            'success': True,
            'message': '验证码已发送，请查收邮件',
            'expires_in': 600  # 10分钟
        })

    except ValueError as e:
        # SMTP未配置
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': f'发送失败: {str(e)}'}), 500


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    POST /api/auth/register - Register a new user

    Request body:
    {
        "username": "user123",
        "password": "password123",
        "email": "user@example.com",
        "verification_code": "123456",  // 如果启用邮箱验证则必填
        "referral_code": "ABCD1234"     // 可选，邀请码
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip().lower() or None
    verification_code = data.get('verification_code', '').strip()
    referral_code = data.get('referral_code', '').strip().upper() or None

    # 获取系统设置
    settings = SystemSettings.get_settings()

    # Validation
    if not username:
        return jsonify({'error': 'Username is required'}), 400

    if len(username) < 3 or len(username) > 50:
        return jsonify({'error': 'Username must be 3-50 characters'}), 400

    if not password:
        return jsonify({'error': 'Password is required'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    # 邮箱验证
    if settings.require_email_verification:
        if not email:
            return jsonify({'error': '邮箱地址不能为空'}), 400

        if not is_valid_email(email):
            return jsonify({'error': '邮箱格式不正确'}), 400

        if not verification_code:
            return jsonify({'error': '验证码不能为空'}), 400

        # 验证验证码
        success, message = EmailVerification.verify_code(email, verification_code)
        if not success:
            return jsonify({'error': message}), 400
    else:
        # 不要求邮箱验证时，邮箱仍然要验证格式（如果提供了的话）
        if email and not is_valid_email(email):
            return jsonify({'error': '邮箱格式不正确'}), 400

    # Check if username exists
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409

    # Check if email exists (if provided)
    if email and User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 409

    # Create user (积分体系：tier由积分动态决定)
    user = User(
        username=username,
        email=email,
        email_verified=settings.require_email_verification,  # 如果要求验证，则验证码验证通过即为已验证
        role='user',
        tier='free',  # 初始为free，由积分动态决定实际tier
        premium_expires_at=None,
    )
    user.set_password(password)
    user.ensure_referral_code()  # 生成邀请码

    db.session.add(user)
    db.session.flush()  # 获取用户ID

    # 发放注册赠送积分
    PointsService.grant_register_bonus(user.id)

    # 处理邀请关系（会发放邀请奖励积分）
    if referral_code:
        ReferralService.process_registration_referral(user, referral_code)

    db.session.commit()

    # Generate tokens
    access_token = generate_access_token(user)
    refresh_token = generate_refresh_token(user)

    return jsonify({
        'success': True,
        'message': 'Registration successful',
        'data': {
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
        }
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    # Find user (支持用户名或邮箱登录)
    user = User.query.filter_by(username=username).first()
    if not user:
        # 尝试用邮箱查找
        user = User.query.filter_by(email=username.lower()).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid username or password'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is disabled'}), 403

    # Update last login time
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    # Generate tokens
    access_token = generate_access_token(user)
    refresh_token = generate_refresh_token(user)

    return jsonify({
        'success': True,
        'message': 'Login successful',
        'data': {
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
        }
    })


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logout user (client should discard tokens)"""
    # JWT is stateless, so we just return success
    # Client should remove tokens from storage
    return jsonify({'success': True, 'message': 'Logout successful'})


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_me():
    """Get current user information"""
    user = get_current_user()
    return jsonify({'success': True, 'data': {'user': user.to_dict()}})


@auth_bp.route('/password', methods=['PUT'])
@login_required
def change_password():
    """Change user password"""
    user = get_current_user()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password or not new_password:
        return jsonify({'error': 'Old and new passwords are required'}), 400

    if not user.check_password(old_password):
        return jsonify({'error': 'Current password is incorrect'}), 401

    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400

    user.set_password(new_password)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Password changed successfully'})


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token using refresh token"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    refresh_token_str = data.get('refresh_token', '')

    if not refresh_token_str:
        return jsonify({'error': 'Refresh token is required'}), 400

    try:
        payload = decode_token(refresh_token_str)

        # Verify it's a refresh token
        if payload.get('type') != 'refresh':
            return jsonify({'error': 'Invalid token type'}), 401

        # Get user from database
        user = User.query.get(payload['user_id'])

        if not user:
            return jsonify({'error': 'User not found'}), 401

        if not user.is_active:
            return jsonify({'error': 'User account is disabled'}), 403

        # Generate new access token
        access_token = generate_access_token(user)

        return jsonify({
            'success': True,
            'data': {
                'access_token': access_token,
                'user': user.to_dict(),
            }
        })

    except AuthenticationError as e:
        return jsonify({'error': str(e)}), 401


@auth_bp.route('/check-email', methods=['POST'])
def check_email():
    """
    POST /api/auth/check-email - 检查邮箱是否已注册

    Request body:
    {
        "email": "user@example.com"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': '邮箱地址不能为空'}), 400

    if not is_valid_email(email):
        return jsonify({'error': '邮箱格式不正确'}), 400

    exists = User.query.filter_by(email=email).first() is not None

    return jsonify({
        'success': True,
        'data': {
            'exists': exists
        }
    })


@auth_bp.route('/check-username', methods=['POST'])
def check_username():
    """
    POST /api/auth/check-username - 检查用户名是否已注册

    Request body:
    {
        "username": "user123"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()

    if not username:
        return jsonify({'error': '用户名不能为空'}), 400

    exists = User.query.filter_by(username=username).first() is not None

    return jsonify({
        'success': True,
        'data': {
            'exists': exists
        }
    })


@auth_bp.route('/registration-settings', methods=['GET'])
def get_registration_settings():
    """
    GET /api/auth/registration-settings - 获取注册相关设置（公开接口）
    """
    settings = SystemSettings.get_settings()

    return jsonify({
        'success': True,
        'data': {
            'require_email_verification': settings.require_email_verification,
            'default_user_tier': settings.default_user_tier,
        }
    })
