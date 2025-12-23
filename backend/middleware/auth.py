"""
JWT Authentication Middleware
"""
import os
from functools import wraps
from datetime import datetime, timedelta, timezone

import jwt
from flask import request, jsonify, g, current_app

from models import User


# JWT Configuration
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
JWT_ALGORITHM = 'HS256'


def generate_access_token(user: User) -> str:
    """Generate JWT access token for user"""
    payload = {
        'user_id': user.id,
        'username': user.username,
        'role': user.role,
        'tier': user.tier,
        'exp': datetime.now(timezone.utc) + JWT_ACCESS_TOKEN_EXPIRES,
        'iat': datetime.now(timezone.utc),
        'type': 'access'
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def generate_refresh_token(user: User) -> str:
    """Generate JWT refresh token for user"""
    payload = {
        'user_id': user.id,
        'exp': datetime.now(timezone.utc) + JWT_REFRESH_TOKEN_EXPIRES,
        'iat': datetime.now(timezone.utc),
        'type': 'refresh'
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError('Token has expired')
    except jwt.InvalidTokenError:
        raise AuthenticationError('Invalid token')


class AuthenticationError(Exception):
    """Authentication error"""
    pass


def get_current_user() -> User:
    """Get current authenticated user from request context"""
    return g.get('current_user')


def login_required(f):
    """Decorator to require authentication for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header[7:]  # Remove 'Bearer ' prefix

        try:
            payload = decode_token(token)

            # Verify it's an access token
            if payload.get('type') != 'access':
                return jsonify({'error': 'Invalid token type'}), 401

            # Get user from database
            user = User.query.get(payload['user_id'])

            if not user:
                return jsonify({'error': 'User not found'}), 401

            if not user.is_active:
                return jsonify({'error': 'User account is disabled'}), 403

            # Store user in request context
            g.current_user = user

        except AuthenticationError as e:
            return jsonify({'error': str(e)}), 401

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """Decorator to require admin role for a route"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        user = get_current_user()

        if not user.is_admin():
            return jsonify({'error': 'Admin access required'}), 403

        return f(*args, **kwargs)

    return decorated_function


def premium_required(f):
    """Decorator to require premium subscription for a route"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        user = get_current_user()

        if not user.is_premium_active() and not user.is_admin():
            return jsonify({
                'error': 'Premium subscription required',
                'code': 'PREMIUM_REQUIRED'
            }), 403

        return f(*args, **kwargs)

    return decorated_function


def optional_auth(f):
    """Decorator for routes that can work with or without authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        g.current_user = None

        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            try:
                payload = decode_token(token)
                if payload.get('type') == 'access':
                    user = User.query.get(payload['user_id'])
                    if user and user.is_active:
                        g.current_user = user
            except AuthenticationError:
                pass  # Ignore auth errors for optional auth

        return f(*args, **kwargs)

    return decorated_function
