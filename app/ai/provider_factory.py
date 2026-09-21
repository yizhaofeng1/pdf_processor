"""Factory for registering, creating, and switching Vision Model Providers."""

from typing import Dict, Any, Type, Optional
import logging

from .base import VisionModelProvider
from .gemini_provider import GeminiProvider
from .openai_compat_provider import OpenAICompatProvider
from .claude_provider import ClaudeProvider
from ..storage.key_storage import KeyStorage

logger = logging.getLogger("examsplit.ai.factory")

PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "display_name": "Google Gemini (AI Studio)",
        "default_base_url": "https://generativelanguage.googleapis.com",
        "default_model": "gemini-2.5-flash",
        "provider_class": GeminiProvider,
        "description": "Google AI Studio 原生多模态 API，高性价比与强大多模态能力",
    },
    "deepseek": {
        "display_name": "DeepSeek (深度求索)",
        "default_base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "provider_class": OpenAICompatProvider,
        "description": "DeepSeek 官方兼容接口 (注: 官方 api.deepseek.com 为纯文本；视觉拆题请用兼容视觉代理或选用 Gemini/OpenAI/GLM/Claude)",
    },
    "openai": {
        "display_name": "OpenAI (GPT-4o)",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "provider_class": OpenAICompatProvider,
        "description": "OpenAI 官方通用多模态模型",
    },
    "glm": {
        "display_name": "智谱 GLM (BigModel)",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4v",
        "provider_class": OpenAICompatProvider,
        "description": "智谱清言多模态大模型",
    },
    "claude": {
        "display_name": "Anthropic Claude",
        "default_base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-5-sonnet-20241022",
        "provider_class": ClaudeProvider,
        "description": "Anthropic 原生 Messages 接口",
    },
    "custom": {
        "display_name": "自定义网关 / 代理 (OpenAI 兼容)",
        "default_base_url": "https://your-custom-gateway.com/v1",
        "default_model": "gpt-4o",
        "provider_class": OpenAICompatProvider,
        "description": "兼容 OneAPI, NewAPI 或第三方反代网关",
    },
}


class ProviderFactory:
    """Instantiates VisionModelProvider based on identifier and configuration."""

    @classmethod
    def get_presets(cls) -> Dict[str, Dict[str, Any]]:
        return PROVIDER_PRESETS

    @classmethod
    def create_provider(
        cls,
        provider_id: str,
        base_url: Optional[str] = None,
        api_key: str = "",
        model_name: Optional[str] = None,
        timeout: float = 60.0,
        proxy: str = "",
    ) -> VisionModelProvider:
        """Create provider instance using given or preset default parameters."""
        preset = PROVIDER_PRESETS.get(provider_id, PROVIDER_PRESETS["custom"])
        provider_cls = preset["provider_class"]

        resolved_url = (base_url or preset["default_base_url"]).strip()
        resolved_model = (model_name or preset["default_model"]).strip()

        logger.info(f"Creating AI Provider: {provider_id} (model: {resolved_model}, url: {resolved_url})")

        return provider_cls(
            provider_id=provider_id,
            base_url=resolved_url,
            api_key=api_key.strip(),
            model_name=resolved_model,
            timeout=timeout,
            proxy=proxy.strip(),
        )

    @classmethod
    def get_active_provider(cls) -> VisionModelProvider:
        """Load encrypted configuration and create currently active default provider."""
        all_configs = KeyStorage.get_all_configs()
        default_id = KeyStorage.get_default_provider_id()
        global_proxy = all_configs.get("proxy", "")

        cfg = KeyStorage.get_provider_config(default_id) or {}

        preset = PROVIDER_PRESETS.get(default_id, PROVIDER_PRESETS["gemini"])
        base_url = cfg.get("base_url") or preset["default_base_url"]
        api_key = cfg.get("api_key") or ""
        model_name = cfg.get("model_name") or preset["default_model"]
        timeout = float(cfg.get("timeout") or 60.0)
        proxy = cfg.get("proxy") or global_proxy

        return cls.create_provider(
            provider_id=default_id,
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
            proxy=proxy,
        )
