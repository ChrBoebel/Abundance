"""Validated Abundance runtime settings without orchestration-framework types."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator


class AbundanceSettings(BaseModel):
    """Non-secret application and provider limits."""

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:4290", "http://localhost:3000"]
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    planning_model_max_tokens: int = Field(default=3000, ge=256, le=16000)
    assessment_model_max_tokens: int = Field(default=5000, ge=256, le=16000)
    synthesis_model_max_tokens: int = Field(default=12000, ge=512, le=64000)
    assessment_batch_size: int = Field(default=8, ge=1, le=12)
    assessment_max_evidence: int = Field(default=24, ge=1, le=60)
    assessment_excerpt_chars: int = Field(default=2500, ge=500, le=12000)
    evidence_assessment_mode: Literal["off", "shadow"] = "shadow"
    provider_timeout_seconds: float = Field(default=90.0, ge=5.0, le=300.0)
    provider_max_retries: int = Field(default=2, ge=0, le=6)
    search_timeout_seconds: float = Field(default=45.0, ge=5.0, le=120.0)
    max_evidence_excerpt_chars: int = Field(default=12000, ge=500, le=50000)
    internal_api_token: SecretStr | None = None
    database_url: SecretStr | None = None
    database_pool_min_size: int = Field(default=1, ge=1, le=20)
    database_pool_max_size: int = Field(default=10, ge=1, le=100)
    share_base_url: str = "http://localhost:4290/shared"
    log_level: str = "INFO"
    deployment_environment: Literal["development", "test", "staging", "production"] = "development"

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, values: list[str]) -> list[str]:
        """Require explicit HTTP(S) origins and reject wildcard credentials policy."""
        normalized = list(dict.fromkeys(value.strip().rstrip("/") for value in values if value.strip()))
        if not normalized or "*" in normalized:
            raise ValueError("cors_origins must contain explicit origins")
        if any(not value.startswith(("http://", "https://")) for value in normalized):
            raise ValueError("cors_origins must use http or https")
        return normalized

    @field_validator("internal_api_token")
    @classmethod
    def validate_internal_token(cls, value: SecretStr | None) -> SecretStr | None:
        """Require enough entropy for the optional service-to-service bearer token."""
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("internal_api_token must contain at least 32 characters")
        return value

    @field_validator("database_pool_max_size")
    @classmethod
    def validate_pool_bounds(cls, value: int, info: Any) -> int:
        """Keep the maximum connection count above the configured minimum."""
        minimum = info.data.get("database_pool_min_size", 1)
        if value < minimum:
            raise ValueError("database_pool_max_size must be at least database_pool_min_size")
        return value

    @field_validator("share_base_url")
    @classmethod
    def validate_share_base_url(cls, value: str) -> str:
        """Require an absolute HTTP(S) base without a trailing slash."""
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("share_base_url must use http or https")
        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize supported structured-log levels."""
        normalized = value.strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("log_level is not supported")
        return normalized

    @model_validator(mode="after")
    def require_production_boundaries(self) -> AbundanceSettings:
        """Fail closed when a network deployment omits internal authentication."""
        if self.deployment_environment in {"staging", "production"} and self.internal_api_token is None:
            raise ValueError("internal_api_token is required in staging and production")
        return self

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> AbundanceSettings:
        """Load documented `ABUNDANCE_*` variables and no legacy aliases."""
        source = environment if environment is not None else os.environ
        values: dict[str, Any] = {}
        for field_name in cls.model_fields:
            raw = source.get(f"ABUNDANCE_{field_name.upper()}")
            if raw is None:
                continue
            if field_name in {"internal_api_token", "database_url"} and not raw.strip():
                continue
            values[field_name] = (
                [item.strip() for item in raw.split(",")]
                if field_name == "cors_origins"
                else raw
            )
        return cls.model_validate(values)
