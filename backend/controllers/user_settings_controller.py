"""
User Settings Controller - handles user-specific settings endpoints
"""
from flask import Blueprint, request
from models import db, UserSettings, User
from utils import success_response, error_response, not_found, bad_request
from middleware import login_required, get_current_user
from datetime import datetime

user_settings_bp = Blueprint('user_settings', __name__, url_prefix='/api/user')


@user_settings_bp.route('/settings', methods=['GET'])
@login_required
def get_user_settings():
    """
    GET /api/user/settings - 获取当前用户设置
    """
    try:
        current_user = get_current_user()
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()

        if not settings:
            # 创建默认设置
            settings = UserSettings(user_id=current_user.id)
            db.session.add(settings)
            db.session.commit()

        return success_response(settings.to_dict())

    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@user_settings_bp.route('/settings', methods=['PUT'])
@login_required
def update_user_settings():
    """
    PUT /api/user/settings - 更新当前用户设置

    Body:
    {
        "ai_provider_format": "openai" | "gemini",
        "api_base_url": "https://...",
        "api_key": "sk-...",
        "text_model": "gpt-4",
        "image_model": "dall-e-3",
        "image_caption_model": "gpt-4-vision"
    }
    """
    try:
        current_user = get_current_user()
        data = request.get_json() or {}

        settings = UserSettings.query.filter_by(user_id=current_user.id).first()

        if not settings:
            settings = UserSettings(user_id=current_user.id)
            db.session.add(settings)

        # 更新字段
        if 'ai_provider_format' in data:
            if data['ai_provider_format'] not in ['openai', 'gemini']:
                return bad_request("ai_provider_format must be 'openai' or 'gemini'")
            settings.ai_provider_format = data['ai_provider_format']

        if 'api_base_url' in data:
            settings.api_base_url = data['api_base_url'] or None

        if 'api_key' in data:
            # 只有非空时才更新
            if data['api_key']:
                settings.api_key = data['api_key']

        if 'text_model' in data:
            settings.text_model = data['text_model'] or None

        if 'image_model' in data:
            settings.image_model = data['image_model'] or None

        if 'image_caption_model' in data:
            settings.image_caption_model = data['image_caption_model'] or None

        settings.updated_at = datetime.utcnow()
        db.session.commit()

        return success_response(settings.to_dict(), message="设置已更新")

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@user_settings_bp.route('/profile', methods=['GET'])
@login_required
def get_user_profile():
    """
    GET /api/user/profile - 获取当前用户信息
    """
    try:
        current_user = get_current_user()
        return success_response(current_user.to_dict())
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@user_settings_bp.route('/profile', methods=['PUT'])
@login_required
def update_user_profile():
    """
    PUT /api/user/profile - 更新用户信息

    Body:
    {
        "email": "user@example.com"
    }
    """
    try:
        current_user = get_current_user()
        data = request.get_json() or {}

        if 'email' in data:
            email = data['email']
            if email:
                # 检查邮箱是否已被使用
                existing = User.query.filter(User.email == email, User.id != current_user.id).first()
                if existing:
                    return bad_request("该邮箱已被其他用户使用")
            current_user.email = email or None

        current_user.updated_at = datetime.utcnow()
        db.session.commit()

        return success_response(current_user.to_dict(), message="资料已更新")

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)
