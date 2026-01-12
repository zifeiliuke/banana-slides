"""
User settings API key behavior:
- sending api_key="" clears saved key
- leaving api_key absent keeps existing
"""

import uuid

from models import db, User


def _create_user(username: str, password: str = "password") -> User:
    user = User(username=username, email=f"{username}@example.com", role="user")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, username: str, password: str = "password") -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data and data.get("success") is True
    return data["data"]["access_token"]


class TestUserSettingsApiKeyClear:
    def test_user_settings_api_key_can_be_cleared(self, client):
        username = f"u_{uuid.uuid4().hex[:8]}"
        _create_user(username)
        token = _login(client, username)

        # Set a key
        resp = client.put(
            "/api/user/settings",
            json={"api_key": "sk-test-key", "ai_provider_format": "openai"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data and data.get("success") is True
        assert data["data"]["api_key_length"] > 0

        # Clear the key
        resp = client.put(
            "/api/user/settings",
            json={"api_key": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data and data.get("success") is True
        assert data["data"]["api_key_length"] == 0

