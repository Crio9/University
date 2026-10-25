import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_live_ai(monkeypatch):
    # Tests must never spend a real key inherited from the developer's environment.
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "")
