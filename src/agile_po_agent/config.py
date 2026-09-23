"""Runtime settings loaded from environment variables."""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Secrets are injected at runtime and never read from repository files by default."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    openai_api_key: str | None = None
    openai_cheap_model: str = "gpt-4.1-mini"
    openai_heavy_model: str = "gpt-4.1"

    typesafe_api_key: str | None = None
    typesafe_api_url: str = "https://api.typesafe.ai/v1/systemone"
    typesafe_model: str = "jev-latest"
    typesafe_environment: str | None = None
    typesafe_timeout_seconds: float = Field(default=10.0, gt=0.0, le=60.0)
    typesafe_max_response_bytes: int = Field(default=1_000_000, ge=1_024, le=10_000_000)
    jev_choice_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None

    ready_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    quality_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_steps: int = Field(default=3, ge=1, le=10)
    noul_no_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    noul_yes_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_noul_thresholds(self) -> "Settings":
        if self.noul_no_threshold >= self.noul_yes_threshold:
            raise ValueError("NOUL_NO_THRESHOLD must be lower than NOUL_YES_THRESHOLD")
        return self
