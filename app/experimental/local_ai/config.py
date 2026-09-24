"""Configuration parameters and paths for the local AI pipeline."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "local"


class LocalModelConfig(BaseModel):
    """Runtime configuration for local models and services."""
    # VLM Endpoint settings (OpenAI-compatible local server, e.g. Ollama or llama-server)
    endpoint_url: str = "http://127.0.0.1:11434/v1"
    vlm_model: str = "qwen2.5vl:3b"
    api_key: str = "local"
    timeout_seconds: float = 30.0
    max_retries: int = 2

    # Mode: "normal" (rules + VLM verification on low confidence), "fast" (rules only, no VLM)
    mode: str = "normal"  # "normal" | "fast"

    # Layout backend: "auto", "native", "paddle"
    layout_backend: str = "auto"

    # OCR backend: "auto", "native_only", "ocr_only", "hybrid"
    ocr_backend: str = "auto"

    # Confidence threshold below which candidate is routed to VLM review
    confidence_threshold: float = 0.85

    # Safety padding ratios (relative to page width and height)
    pad_ratio_x: float = 0.015
    pad_ratio_y: float = 0.010

    # Paths
    models_dir: Path = MODELS_DIR
    prompts_dir: Path = PROMPTS_DIR

    model_config = {
        "arbitrary_types_allowed": True,
    }


def get_default_config() -> LocalModelConfig:
    """Get default local AI configuration."""
    return LocalModelConfig()
