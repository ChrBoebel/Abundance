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
