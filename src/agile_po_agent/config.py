"""Runtime settings loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Secrets are injected at runtime and never read from repository files by default."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    openai_api_key: str | None = None
    openai_cheap_model: str = "gpt-4.1-mini"
    openai_heavy_model: str = "gpt-4.1"

    typesafe_api_key: str | None = None
    typesafe_api_url: str | None = None
    typesafe_model: str = "jev-latest"

    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None

    ready_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    quality_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_steps: int = Field(default=3, ge=1, le=10)

