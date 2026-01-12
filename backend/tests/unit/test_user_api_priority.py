"""
Tests for API selection priority:

- If a user configured their own API Key, it should be used first.
- System API should only be used when the user's API info is empty.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import uuid


def _create_user(db_session, *, role: str = "user") -> User:
    from models import User

    user = User(
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )
    user.set_password("password")
    db_session.add(user)
    db_session.commit()
    return user


def _grant_points(db_session, user: User, remaining: int = 10):
    from models.points import PointsBalance

    balance = PointsBalance(
        user_id=user.id,
        amount=remaining,
        remaining=remaining,
        source=PointsBalance.SOURCE_ADMIN_GRANT,
        expires_at=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(balance)
    db_session.commit()


class TestSystemApiPriority:
    def test_premium_user_with_own_api_uses_own_api(self, db_session):
        from models import UserSettings
        from services.usage_service import UsageService

        user = _create_user(db_session)
        _grant_points(db_session, user, remaining=10)  # premium

        settings = UserSettings(user_id=user.id, api_key="user-key", ai_provider_format="openai")
        db_session.add(settings)
        db_session.commit()

        assert UsageService.is_using_system_api(user) is False

    def test_premium_user_without_own_api_uses_system_api(self, db_session):
        from services.usage_service import UsageService

        user = _create_user(db_session)
        _grant_points(db_session, user, remaining=10)  # premium

        assert UsageService.is_using_system_api(user) is True

    def test_admin_always_uses_system_api_even_with_own_api(self, db_session):
        from models import UserSettings
        from services.usage_service import UsageService

        user = _create_user(db_session, role="admin")
        _grant_points(db_session, user, remaining=10)

        settings = UserSettings(user_id=user.id, api_key="user-key", ai_provider_format="openai")
        db_session.add(settings)
        db_session.commit()

        assert UsageService.is_using_system_api(user) is True

    def test_get_ai_service_uses_user_settings_when_present(self, db_session):
        from models import UserSettings
        from services.ai_service import get_ai_service_for_user

        user = _create_user(db_session)
        _grant_points(db_session, user, remaining=10)  # premium

        settings = UserSettings(user_id=user.id, api_key="user-key", ai_provider_format="openai")
        db_session.add(settings)
        db_session.commit()

        with patch("services.ai_service.AIService") as AIServiceMock:
            instance = MagicMock()
            instance.text_provider = MagicMock()
            AIServiceMock.return_value = instance

            _ = get_ai_service_for_user(user)

            assert AIServiceMock.call_count == 1
            _, kwargs = AIServiceMock.call_args
            assert "config_override" in kwargs
            assert kwargs["config_override"]["api_key"] == "user-key"

    def test_get_ai_service_falls_back_to_system_when_user_api_empty(self, db_session):
        from services.ai_service import get_ai_service_for_user

        user = _create_user(db_session)
        _grant_points(db_session, user, remaining=10)  # premium

        with patch("services.ai_service.AIService") as AIServiceMock:
            instance = MagicMock()
            instance.text_provider = MagicMock()
            AIServiceMock.return_value = instance

            _ = get_ai_service_for_user(user)

            assert AIServiceMock.call_count == 1
            args, kwargs = AIServiceMock.call_args
            assert args == ()
            assert kwargs == {}
