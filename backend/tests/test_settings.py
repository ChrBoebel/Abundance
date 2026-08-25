import pytest
from pydantic import ValidationError

from abundance_research.settings import AbundanceSettings


def test_settings_load_only_prefixed_environment_values() -> None:
    settings = AbundanceSettings.from_environment(
        {
            "PROVIDER_MAX_RETRIES": "6",
            "ABUNDANCE_PROVIDER_MAX_RETRIES": "4",
            "ABUNDANCE_CORS_ORIGINS": "https://app.example.org, http://localhost:4290/",
        }
    )

    assert settings.provider_max_retries == 4
    assert settings.cors_origins == ["https://app.example.org", "http://localhost:4290"]


def test_settings_reject_wildcard_cors_origin() -> None:
    with pytest.raises(ValidationError):
        AbundanceSettings(cors_origins=["*"])


def test_settings_reject_short_internal_api_token() -> None:
    with pytest.raises(ValidationError):
        AbundanceSettings(internal_api_token="too-short")


def test_settings_treat_empty_internal_api_token_as_omitted() -> None:
    settings = AbundanceSettings.from_environment({"ABUNDANCE_INTERNAL_API_TOKEN": "  "})

    assert settings.internal_api_token is None


def test_settings_validate_database_pool_and_share_boundary() -> None:
    settings = AbundanceSettings.from_environment(
        {
            "ABUNDANCE_DATABASE_URL": "postgresql://user:secret@db/abundance",
            "ABUNDANCE_DATABASE_POOL_MIN_SIZE": "2",
            "ABUNDANCE_DATABASE_POOL_MAX_SIZE": "8",
            "ABUNDANCE_SHARE_BASE_URL": "https://app.example.org/shared/",
            "ABUNDANCE_LOG_LEVEL": "warning",
        }
    )

    assert settings.database_url is not None
    assert settings.database_pool_min_size == 2
    assert settings.database_pool_max_size == 8
    assert settings.share_base_url == "https://app.example.org/shared"
    assert settings.log_level == "WARNING"


def test_settings_reject_database_pool_inversion() -> None:
    with pytest.raises(ValidationError):
        AbundanceSettings(database_pool_min_size=5, database_pool_max_size=2)


def test_network_deployment_requires_internal_api_token() -> None:
    with pytest.raises(ValidationError):
        AbundanceSettings(deployment_environment="production")
