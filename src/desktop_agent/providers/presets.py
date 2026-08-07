from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderPreset:
    id: str
    display_name: str
    base_url: str
    model_hints: tuple[str, ...]
    discovery_supported: bool = True


PROVIDER_PRESETS = (
    ProviderPreset("openai", "OpenAI", "https://api.openai.com/v1", ("gpt-5", "gpt-4.1")),
    ProviderPreset(
        "gemini", "Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", ("gemini-2.5-pro",)
    ),
    ProviderPreset("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", ("openai/gpt-5",)),
    ProviderPreset("ollama", "Ollama", "http://127.0.0.1:11434/v1", ("qwen3", "deepseek-r1")),
    ProviderPreset("deepseek", "DeepSeek", "https://api.deepseek.com/v1", ("deepseek-chat",)),
    ProviderPreset(
        "bailian", "Alibaba Cloud Bailian", "https://dashscope.aliyuncs.com/compatible-mode/v1", ("qwen-plus",)
    ),
    ProviderPreset("moonshot", "Moonshot", "https://api.moonshot.cn/v1", ("kimi-k2",)),
    ProviderPreset("zhipu", "Zhipu AI", "https://open.bigmodel.cn/api/paas/v4", ("glm-4.5",)),
    ProviderPreset("siliconflow", "SiliconFlow", "https://api.siliconflow.cn/v1", ("deepseek-ai/DeepSeek-V3",)),
)

PRESETS_BY_ID = {preset.id: preset for preset in PROVIDER_PRESETS}
