from abundance_research.settings import AbundanceSettings, SearchProvider


def test_settings_accept_product_level_runtime_config() -> None:
    settings = AbundanceSettings.from_runnable_config(
        {
            "configurable": {
                "search_provider": "tavily",
                "max_coordination_iterations": 5,
                "max_search_iterations": 8,
            }
        }
    )

    assert settings.search_provider is SearchProvider.TAVILY
    assert settings.max_coordination_iterations == 5
    assert settings.max_search_iterations == 8


def test_abundance_environment_prefix_takes_precedence(monkeypatch) -> None:
    monkeypatch.setenv("ABUNDANCE_MAX_SEARCH_ITERATIONS", "6")

    settings = AbundanceSettings.from_runnable_config(
        {"configurable": {"max_search_iterations": 2}}
    )

    assert settings.max_search_iterations == 6
