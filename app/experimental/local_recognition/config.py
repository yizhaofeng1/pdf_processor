"""Configuration compatibility wrapper for local recognition."""

from ..local_ai.config import LocalModelConfig, get_default_config, MODELS_DIR, PROMPTS_DIR

__all__ = [
    "LocalModelConfig",
    "get_default_config",
    "MODELS_DIR",
    "PROMPTS_DIR",
]
