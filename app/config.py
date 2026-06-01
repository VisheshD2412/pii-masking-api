"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the PII masking API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="PII Masking API", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    workers: int = Field(default=1, alias="WORKERS")

    max_text_length: int = Field(default=5000, alias="MAX_TEXT_LENGTH")
    large_text_threshold: int = Field(default=2000, alias="LARGE_TEXT_THRESHOLD")

    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_max_size: int = Field(default=1024, alias="CACHE_MAX_SIZE")

    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit: str = Field(default="60/minute", alias="RATE_LIMIT")

    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8501", "*"],
        alias="CORS_ORIGINS",
    )

    spacy_model: str = Field(default="en_core_web_sm", alias="SPACY_MODEL")
    default_language: str = Field(default="en", alias="DEFAULT_LANGUAGE")
    score_threshold: float = Field(default=0.35, alias="SCORE_THRESHOLD")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_requests: bool = Field(default=True, alias="LOG_REQUESTS")

    prometheus_enabled: bool = Field(default=True, alias="PROMETHEUS_ENABLED")

    supported_entities: List[str] = Field(
        default=[
            "PERSON",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "US_SSN",
            "CREDIT_CARD",
            "LOCATION",
            "DATE_TIME",
            "US_DRIVER_LICENSE",
            "US_BANK_NUMBER",
            "IN_AADHAAR",
            "IN_PAN",
            "IN_VOTER_ID",
            "IN_DRIVER_LICENSE",
        ],
        alias="SUPPORTED_ENTITIES",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
