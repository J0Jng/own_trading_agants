"""Shared model catalog for CLI selections and validation."""

from __future__ import annotations

ModelOption = tuple[str, str]
ProviderModeOptions = dict[str, dict[str, list[ModelOption]]]

# Providers that serve many / frequently-changing models: offer only "Custom
# model ID" rather than a list that goes stale.
_CUSTOM_ONLY: dict[str, list[ModelOption]] = {
    "quick": [("Custom model ID", "custom")],
    "deep": [("Custom model ID", "custom")],
}


# Shared model list for GLM via Z.AI (international) and BigModel (China).
# Source: docs.z.ai (GLM Coding Plan supported models + LLM guides).
# All GLM 4.7+ entries support thinking mode via thinking={"type":"enabled"}.
_GLM_MODELS: dict[str, list[ModelOption]] = {
    "quick": [
        ("GLM-5-Turbo - Fast, switchable thinking modes", "glm-5-turbo"),
        ("GLM-4.7 - Previous-gen flagship", "glm-4.7"),
        ("GLM-4.5-Air - Lightweight, cost-efficient", "glm-4.5-air"),
        ("Custom model ID", "custom"),
    ],
    "deep": [
        ("GLM-5.2 - Latest flagship, 1M ctx", "glm-5.2"),
        ("GLM-5.1 - 745B, 200K ctx", "glm-5.1"),
        ("GLM-5 - Flagship, 204K ctx", "glm-5"),
        ("GLM-4.7 - Previous-gen flagship", "glm-4.7"),
        ("Custom model ID", "custom"),
    ],
}


# Shared model list for Qwen's global (dashscope-intl) and CN (dashscope) endpoints.
# Source: modelstudio.console.alibabacloud.com (Featured Models — Flagship + Cost-optimized).
_QUEN_MODELS: dict[str, list[ModelOption]] = {
    "quick": [
        ("Qwen 3.7 Plus - Latest, balanced speed/cost", "qwen3.7-plus"),
        ("Qwen 3.6 Plus - Previous-gen balanced", "qwen3.6-plus"),
        ("Custom model ID", "custom"),
    ],
    "deep": [
        ("Qwen 3.7 Max - Latest flagship, most intelligent, 1M ctx", "qwen3.7-max"),
        ("Qwen 3.6 Max - Previous-gen flagship", "qwen3.6-max"),
        ("Qwen 3.7 Plus - Balanced alternative", "qwen3.7-plus"),
        ("Custom model ID", "custom"),
    ],
}


# Shared model list for MiniMax's global and CN endpoints (same IDs).
# Source: platform.minimax.io/docs/api-reference/text-openai-api.
# M3 carries a 1M-token context window; the M2.x line is 204,800 tokens.
_MINIMAX_MODELS: dict[str, list[ModelOption]] = {
    "quick": [
        ("MiniMax-M3 - Latest, 1M ctx, native multimodal", "MiniMax-M3"),
        ("MiniMax-M2.7-highspeed - Fast M2.7, 204K ctx, ~100 TPS", "MiniMax-M2.7-highspeed"),
        ("MiniMax-M2.5-highspeed - Previous-gen highspeed, 204K ctx", "MiniMax-M2.5-highspeed"),
        ("Custom model ID", "custom"),
    ],
    "deep": [
        ("MiniMax-M3 - Latest flagship, 1M ctx, multimodal coding/agent", "MiniMax-M3"),
        ("MiniMax-M2.7 - Previous flagship, 204K ctx", "MiniMax-M2.7"),
        ("MiniMax-M2.7-highspeed - Same quality as M2.7, ~100 TPS", "MiniMax-M2.7-highspeed"),
        ("MiniMax-M2.5 - Earlier flagship, 204K ctx", "MiniMax-M2.5"),
        ("Custom model ID", "custom"),
    ],
}


# Shared model list for Volcengine Ark "Coding Plan" (provider key: codingplan).
# Model names are fixed — Coding Plan does NOT support "Auto" mode; add a model
# by switching it in the console. Source: docs.volcengine.com "其他工具 / Core
# configuration" (OpenAI-compatible protocol, /api/coding/v3). ark-code-latest
# resolves to whichever model is currently selected in the console, so it is
# offered first and pinned by default in default_config.
_CODINGPLAN_MODELS: dict[str, list[ModelOption]] = {
    "quick": [
        ("ark-code-latest — console-selected model (default)", "ark-code-latest"),
        ("deepseek-v4-flash - Fast DeepSeek", "deepseek-v4-flash"),
        ("glm-5.3-flash - Lightweight GLM", "glm-5.3-flash"),
        ("doubao-seed-2.0-lite - Lite Doubao", "doubao-seed-2.0-lite"),
        ("Custom model ID", "custom"),
    ],
    "deep": [
        ("ark-code-latest — console-selected model (default)", "ark-code-latest"),
        ("doubao-seed-2.1-turbo - Doubao turbo", "doubao-seed-2.1-turbo"),
        ("doubao-seed-2.0-lite - Lite Doubao", "doubao-seed-2.0-lite"),
        ("doubao-seed-evolving - Evolving Doubao", "doubao-seed-evolving"),
        ("deepseek-v4-pro - DeepSeek Pro", "deepseek-v4-pro"),
        ("deepseek-v4-flash - Fast DeepSeek", "deepseek-v4-flash"),
        ("glm-5.3 - GLM flagship", "glm-5.3"),
        ("glm-5.3-flash - Lightweight GLM", "glm-5.3-flash"),
        ("kimi-k2.7-code - Kimi code", "kimi-k2.7-code"),
        ("minimax-m3 - MiniMax M3", "minimax-m3"),
        ("Custom model ID", "custom"),
    ],
}


MODEL_OPTIONS: ProviderModeOptions = {
    "openai": {
        "quick": [
            ("GPT-5.4 Mini - Fast, strong coding and tool use", "gpt-5.4-mini"),
            ("GPT-5.4 Nano - Cheapest, high-volume tasks", "gpt-5.4-nano"),
            ("GPT-5.5 - Latest frontier, 1M context", "gpt-5.5"),
        ],
        "deep": [
            ("GPT-5.5 - Latest frontier, 1M context", "gpt-5.5"),
            ("GPT-5.4 - Previous-gen frontier, 1M context, cost-effective", "gpt-5.4"),
            ("GPT-5.2 - Strong reasoning, cost-effective", "gpt-5.2"),
            ("GPT-5.5 Pro - Most capable, expensive ($30/$180 per 1M tokens)", "gpt-5.5-pro"),
        ],
    },
    "anthropic": {
        "quick": [
            ("Claude Sonnet 5 - Best speed and intelligence balance", "claude-sonnet-5"),
            ("Claude Haiku 4.5 - Fastest with near-frontier intelligence", "claude-haiku-4-5"),
        ],
        "deep": [
            ("Claude Fable 5 - Most capable, long-running agents", "claude-fable-5"),
            ("Claude Opus 4.8 - Frontier agentic coding and reasoning", "claude-opus-4-8"),
            ("Claude Sonnet 5 - Near-frontier intelligence at Sonnet cost", "claude-sonnet-5"),
            ("Claude Opus 4.7 - Previous frontier, long-running agents", "claude-opus-4-7"),
        ],
    },
    "google": {
        "quick": [
            ("Gemini 3.5 Flash - Latest, frontier agentic + coding (GA)", "gemini-3.5-flash"),
            ("Gemini 3.1 Flash Lite - Most cost-efficient", "gemini-3.1-flash-lite"),
        ],
        "deep": [
            ("Gemini 3.1 Pro - Reasoning-first, complex workflows (preview)", "gemini-3.1-pro-preview"),
            ("Gemini 3.5 Flash - Latest GA, strong agentic + coding", "gemini-3.5-flash"),
        ],
    },
    "xai": {
        "quick": [
            ("Grok 4.3 - Latest flagship, fast with built-in reasoning", "grok-4.3"),
            ("Grok 4.20 (Non-Reasoning) - Speed-optimized", "grok-4.20-0309-non-reasoning"),
            ("Grok Build 0.1 - Coding-specialized, 256K ctx", "grok-build-0.1"),
        ],
        "deep": [
            ("Grok 4.3 - Latest flagship, built-in reasoning, 1M ctx", "grok-4.3"),
            ("Grok 4.20 (Reasoning) - Previous-gen reasoning", "grok-4.20-0309-reasoning"),
            ("Grok 4.20 Multi-Agent - Multi-agent reasoning", "grok-4.20-multi-agent-0309"),
        ],
    },
    # DeepSeek: the deepseek-chat / deepseek-reasoner aliases are deprecated
    # and now map to V4 Flash; expose the V4 IDs directly. V4 Flash serves both
    # thinking and non-thinking modes.
    "deepseek": {
        "quick": [
            ("DeepSeek V4 Flash - Latest fast model, thinking + non-thinking", "deepseek-v4-flash"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("DeepSeek V4 Pro - Latest flagship", "deepseek-v4-pro"),
            ("DeepSeek V4 Flash - Fast, supports thinking", "deepseek-v4-flash"),
            ("Custom model ID", "custom"),
        ],
    },
    # Qwen: same model IDs across global and China endpoints, shared list.
    "qwen": _QUEN_MODELS,
    "qwen-cn": _QUEN_MODELS,
    # GLM: Z.AI (international) and BigModel (China) host same IDs, shared list.
    "glm": _GLM_MODELS,
    "glm-cn": _GLM_MODELS,
    # MiniMax: same model IDs across global (.io) and China (.com) regions.
    "minimax": _MINIMAX_MODELS,
    "minimax-cn": _MINIMAX_MODELS,
    "ollama": {
        "quick": [
            ("Qwen3:latest (8B)", "qwen3:latest"),
            ("GPT-OSS:latest (20B)", "gpt-oss:latest"),
            ("GLM-4.7-Flash:latest (30B)", "glm-4.7-flash:latest"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("GLM-4.7-Flash:latest (30B)", "glm-4.7-flash:latest"),
            ("GPT-OSS:latest (20B)", "gpt-oss:latest"),
            ("Qwen3:latest (8B)", "qwen3:latest"),
            ("Custom model ID", "custom"),
        ],
    },
    # Generic OpenAI-compatible endpoint: the model is whatever the user's
    # server serves, so only "Custom model ID" is offered.
    "openai_compatible": _CUSTOM_ONLY,
    # Hosted OpenAI-compatible providers that serve many (and frequently
    # changing) models — offer "Custom model ID" rather than a list that goes
    # stale. The endpoint + key are wired by the provider; the user picks the
    # model their account has access to.
    "mistral": _CUSTOM_ONLY,
    "kimi": _CUSTOM_ONLY,
    "groq": _CUSTOM_ONLY,
    "nvidia": _CUSTOM_ONLY,
    # Coding Plan (Volcengine Ark): fixed list of officially supported models
    # (no "Auto" mode); ark-code-latest resolves to the console-selected model.
    "codingplan": _CODINGPLAN_MODELS,
    # Bedrock model IDs / cross-region inference profile IDs are user-specified.
    "bedrock": _CUSTOM_ONLY,
    # OpenCode Go gateway serves many (and frequently changing) models
    # (DeepSeek/MiniMax/Qwen/GLM/Kimi...) — offer "Custom model ID" rather
    # than a list that goes stale. Endpoint + key are wired by the provider.
    "opencode": _CUSTOM_ONLY,
}


def get_model_options(provider: str, mode: str) -> list[ModelOption]:
    """Return shared model options for a provider and selection mode."""
    return MODEL_OPTIONS[provider.lower()][mode]


def get_known_models() -> dict[str, list[str]]:
    """Build known model names from the shared CLI catalog."""
    return {
        provider: sorted(
            {
                value
                for options in mode_options.values()
                for _, value in options
            }
        )
        for provider, mode_options in MODEL_OPTIONS.items()
    }