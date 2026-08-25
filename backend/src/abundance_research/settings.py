"""Validated Abundance runtime settings without orchestration-framework types."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, SecretStr, field_validator


class AbundanceSettings(BaseModel):
    """Non-secret application and provider limits."""

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:4290", "http://localhost:3000"]
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    planning_model_max_tokens: int = Field(default=3000, ge=256, le=16000)
    synthesis_model_max_tokens: int = Field(default=12000, ge=512, le=64000)
    provider_timeout_seconds: float = Field(default=90.0, ge=5.0, le=300.0)
    provider_max_retries: int = Field(default=2, ge=0, le=6)
    search_timeout_seconds: float = Field(default=45.0, ge=5.0, le=120.0)
    max_evidence_excerpt_chars: int = Field(default=12000, ge=500, le=50000)
    internal_api_token: SecretStr | None = None

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
            if field_name == "internal_api_token" and not raw.strip():
                continue
            values[field_name] = (
                [item.strip() for item in raw.split(",")]
                if field_name == "cors_origins"
                else raw
            )
        return cls.model_validate(values)
