import pytest

from abundance_research.application.errors import ResearchFailure
from abundance_research.bootstrap import build_research_engine


def test_bootstrap_fails_closed_without_provider_credentials() -> None:
    with pytest.raises(ResearchFailure) as caught:
        build_research_engine(environment={})

    assert caught.value.code.value == "configuration_error"
    assert "OPENROUTER" not in caught.value.public_message
