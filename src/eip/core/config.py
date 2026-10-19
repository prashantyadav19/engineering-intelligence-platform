from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EIP_",
        extra="ignore",
    )

    app_name: str = "Engineering Intelligence Platform"
    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: PostgresDsn = PostgresDsn("postgresql+asyncpg://eip:eip@localhost:5432/eip")
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: SecretStr = SecretStr("")
    jira_project_keys: list[str] = []
    jira_story_points_field: str = "customfield_10016"
    jira_sprint_field: str = "customfield_10020"
    jira_webhook_secret: SecretStr = SecretStr("")

    github_token: SecretStr = SecretStr("")
    github_repos: list[str] = []
    github_webhook_secret: SecretStr = SecretStr("")

    aws_region: str = "ap-south-1"
    aws_endpoint_url: str | None = None
    raw_payload_bucket: str = "eip-raw-payloads"
    ingest_queue_name: str = "eip-ingest"


@lru_cache
def get_settings() -> Settings:
    return Settings()
