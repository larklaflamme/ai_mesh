"""Platform settings, read from ``MESH_*`` environment variables and ``.env``.

Nothing is read at import time: call :func:`load_settings` where settings are needed.
"""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MeshSettings(BaseSettings):
    """Platform configuration. Secrets are ``SecretStr`` so they never print by accident."""

    model_config = SettingsConfigDict(
        env_prefix="MESH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    database_url: SecretStr = SecretStr("postgresql+psycopg://mesh_app@127.0.0.1:5432/mesh")
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: SecretStr | None = None
    gateway_url: str = "http://127.0.0.1:8088"
    hidden_root: Path | None = None
    runs_root: Path = Path("runs")
    approver_ssh_key: Path | None = None


def load_settings(**overrides: object) -> MeshSettings:
    """Build settings from the environment (and ``.env``), with optional explicit overrides."""
    return MeshSettings(**overrides)  # type: ignore[arg-type]  # pydantic-settings init kwargs
