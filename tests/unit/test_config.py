import pytest
from pydantic import ValidationError

from eip.core.config import Settings


def test_settings_read_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EIP_ENVIRONMENT", "staging")

    settings = Settings()

    assert settings.environment == "staging"


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EIP_ENVIRONMENT", "prod")

    with pytest.raises(ValidationError):
        Settings()
