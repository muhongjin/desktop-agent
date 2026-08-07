from desktop_agent.providers.presets import PROVIDER_PRESETS


def test_all_provider_presets_have_required_metadata():
    expected = {
        "openai",
        "gemini",
        "openrouter",
        "ollama",
        "deepseek",
        "bailian",
        "moonshot",
        "zhipu",
        "siliconflow",
    }
    assert {preset.id for preset in PROVIDER_PRESETS} == expected
    for preset in PROVIDER_PRESETS:
        assert preset.display_name
        assert preset.base_url.startswith(("http://", "https://"))
        assert preset.model_hints
        assert preset.discovery_supported is True
