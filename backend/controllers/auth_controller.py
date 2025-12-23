"""
Authentication Controller - handles user registration, login, logout
"""
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from models import db, User
from middleware import (
    login_required,
    get_current_user,
    generate_access_token,
    generate_refresh_token,
    decode_token,
    AuthenticationError,
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip() or None

    # Validation
    if not username:
        return jsonify({'error': 'Username is required'}), 400

    if len(username) < 3 or len(username) > 50:
        return jsonify({'error': 'Username must be 3-50 characters'}), 400

    if not password:
        return jsonify({'error': 'Password is required'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    # Check if username exists
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409

    # Check if email exists (if provided)
    if email and User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 409

    # Create user
    user = User(
        username=username,
        email=email,
        role='user',
        tier='free',
    )
    user.set_password(password)

    db.session.add(user)
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

    # Find user
    user = User.query.filter_by(username=username).first()

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
