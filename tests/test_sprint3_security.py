import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.auth import RegisterRequest


def test_public_register_rejects_staff_admin():
    payload = dict(email="user@example.com", password="password", full_name="User")
    for role in ("staff", "admin"):
        with pytest.raises(ValidationError):
            RegisterRequest(**payload, role=role)
    assert RegisterRequest(**payload).role == "student"


def test_insecure_production_config_is_rejected():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", DEBUG=False,
                 JWT_SECRET="change-me-in-production", _env_file=None)
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", DEBUG=True,
                 JWT_SECRET="7b2c90e4f8a1d35b6f2490c17e8a5d32", _env_file=None)


def test_secure_production_config_is_accepted():
    settings = Settings(ENVIRONMENT="production", DEBUG=False,
                        JWT_SECRET="7b2c90e4f8a1d35b6f2490c17e8a5d32", _env_file=None)
    assert settings.DEBUG is False
