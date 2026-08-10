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
        "custom",
    }
    assert {preset.id for preset in PROVIDER_PRESETS} == expected
    for preset in PROVIDER_PRESETS:
        assert preset.display_name
        assert preset.id == "custom" or preset.base_url.startswith(("http://", "https://"))
        assert preset.model_hints
        assert preset.accent_color.startswith("#")
        assert preset.mark
        assert preset.api_protocol in {"chat_completions", "responses"}
        assert preset.discovery_supported is True
    assert next(preset for preset in PROVIDER_PRESETS if preset.id == "openai").api_protocol == (
        "responses"
    )
