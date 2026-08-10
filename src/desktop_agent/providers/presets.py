from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderPreset:
    id: str
    display_name: str
    base_url: str
    model_hints: tuple[str, ...]
    accent_color: str
    mark: str
    api_protocol: str = "chat_completions"
    discovery_supported: bool = True


PROVIDER_PRESETS = (
    ProviderPreset(
        "openai",
        "OpenAI",
        "https://api.openai.com/v1",
        ("gpt-5", "gpt-4.1"),
        "#10a37f",
        "O",
        "responses",
    ),
    ProviderPreset(
        "gemini",
        "Gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        ("gemini-2.5-pro",),
        "#4285f4",
        "G",
    ),
    ProviderPreset(
        "openrouter",
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        ("openai/gpt-5",),
        "#6d5bd0",
        "R",
    ),
    ProviderPreset(
        "ollama",
        "Ollama",
        "http://127.0.0.1:11434/v1",
        ("qwen3", "deepseek-r1"),
        "#4b5563",
        "L",
    ),
    ProviderPreset(
        "deepseek",
        "DeepSeek",
        "https://api.deepseek.com/v1",
        ("deepseek-chat",),
        "#4d6bfe",
        "D",
    ),
    ProviderPreset(
        "bailian",
        "Alibaba Cloud Bailian",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ("qwen-plus",),
        "#ff6a00",
        "A",
    ),
    ProviderPreset(
        "moonshot",
        "Moonshot",
        "https://api.moonshot.cn/v1",
        ("kimi-k2",),
        "#111827",
        "K",
    ),
    ProviderPreset(
        "zhipu",
        "Zhipu AI",
        "https://open.bigmodel.cn/api/paas/v4",
        ("glm-4.5",),
        "#2563eb",
        "Z",
    ),
    ProviderPreset(
        "siliconflow",
        "SiliconFlow",
        "https://api.siliconflow.cn/v1",
        ("deepseek-ai/DeepSeek-V3",),
        "#16a085",
        "S",
    ),
    ProviderPreset("custom", "自定义", "", ("model-id",), "#64748b", "自"),
)

PRESETS_BY_ID = {preset.id: preset for preset in PROVIDER_PRESETS}
