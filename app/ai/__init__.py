"""AI Provider adapters and multimodal vision pipeline."""

from .base import VisionModelProvider, encode_image_base64
from .gemini_provider import GeminiProvider
from .openai_compat_provider import OpenAICompatProvider
from .claude_provider import ClaudeProvider
from .provider_factory import ProviderFactory, PROVIDER_PRESETS
from .prompt_manager import PromptManager
from .response_parser import parse_exam_split_json, ModelOutputError

__all__ = [
    "VisionModelProvider",
    "encode_image_base64",
    "GeminiProvider",
    "OpenAICompatProvider",
    "ClaudeProvider",
    "ProviderFactory",
    "PROVIDER_PRESETS",
    "PromptManager",
    "parse_exam_split_json",
    "ModelOutputError",
]
