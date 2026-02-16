"""Application settings via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings"]


class Settings(BaseSettings):
    """Central configuration — all values from environment."""

    model_config = SettingsConfigDict(env_prefix="CACP_")

    # HMAC signing
    hmac_secret: str = ""

    # GitHub PR creation
    github_token: str = ""
    github_owner: str = "julian-najas"
    github_repo: str = "clinic-gitops-config"

    # Target environment
    environment: str = "dev"

    # OPA
    opa_url: str = "http://localhost:8181"

    # PostgreSQL
    pg_dsn: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # GitHub Webhook
    github_webhook_secret: str = ""
