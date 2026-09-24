import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_models_dir() -> Path:
    """Get the models directory, supporting both dev mode and PyInstaller frozen bundle."""
    if getattr(sys, "frozen", False):
        exe_models = Path(sys.executable).parent / "models"
        if exe_models.exists():
            return exe_models
    return PROJECT_ROOT / "models"


def scan_local_models() -> List[Dict[str, str]]:
    """Scan models directory for GGUF model files and model subdirectories."""
    models_dir = get_models_dir()
    found = []
    if not models_dir.exists():
        return found
    # Scan for .gguf files
    for f in sorted(models_dir.glob("*.gguf")) + sorted(models_dir.glob("*/*.gguf")):
        size_gb = f.stat().st_size / (1024 ** 3)
        found.append({
            "name": f.stem,
            "filename": f.name,
            "path": str(f),
            "size_str": f"{size_gb:.1f} GB" if size_gb >= 0.1 else f"{f.stat().st_size / (1024 ** 2):.0f} MB",
            "type": "gguf",
        })
    # Scan for subdirectories
    for d in sorted(models_dir.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and not any(m["path"].startswith(str(d)) for m in found):
            found.append({
                "name": d.name,
                "filename": d.name,
                "path": str(d),
                "size_str": "目录",
                "type": "dir",
            })
    return found


MODELS_DIR = get_models_dir()
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
