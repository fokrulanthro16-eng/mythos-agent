"""Secure, environment-based settings for the Mythos Autonomous Agent."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ConfigurationError(RuntimeError):
    """Raised when a required runtime setting has not been configured."""


def _read_gemini_api_key() -> SecretStr | None:
    """Read the API key without logging or serializing its value."""
    value = os.getenv("GEMINI_API_KEY", "").strip()
    return SecretStr(value) if value else None


def _default_temp_directory() -> Path:
    """Return the application-owned directory within the OS temp location."""
    return Path(tempfile.gettempdir()) / "mythos_agent"


class Settings(BaseModel):
    """Immutable application settings loaded from the local environment."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    gemini_api_key: SecretStr | None = Field(default_factory=_read_gemini_api_key)
    app_temp_directory: Path = Field(default_factory=_default_temp_directory)

    @property
    def gemini_configured(self) -> bool:
        """Return whether a non-empty Gemini API key is available."""
        return self.gemini_api_key is not None

    def require_gemini_api_key(self) -> str:
        """Return the Gemini key or raise without exposing any secret value."""
        if self.gemini_api_key is None:
            raise ConfigurationError("GEMINI_API_KEY is not configured.")
        return self.gemini_api_key.get_secret_value()


settings = Settings()
