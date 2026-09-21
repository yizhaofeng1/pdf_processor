"""Configuration and defaults for the Local Recognition (VAQL) experiment."""

from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional
from ...config import DATA_DIR, BUNDLE_DIR

# Experiment storage paths
EXPERIMENT_ROOT_DIR = DATA_DIR / "experiments" / "local_recognition"
EXPERIMENT_RUNS_DIR = EXPERIMENT_ROOT_DIR / "runs"
EXPERIMENT_CROPS_DIR = EXPERIMENT_ROOT_DIR / "crops"
EXPERIMENT_RESULTS_DIR = EXPERIMENT_ROOT_DIR / "results"
EXPERIMENT_METRICS_DIR = EXPERIMENT_ROOT_DIR / "metrics"

EXPERIMENT_PROMPTS_DIR = BUNDLE_DIR / "prompts" / "experimental" / "local_recognition"


def ensure_experiment_directories() -> None:
    """Ensure all experiment directories exist."""
    for d in (
        EXPERIMENT_ROOT_DIR,
        EXPERIMENT_RUNS_DIR,
        EXPERIMENT_CROPS_DIR,
        EXPERIMENT_RESULTS_DIR,
        EXPERIMENT_METRICS_DIR,
        EXPERIMENT_PROMPTS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)


class LocalVisionConfig(BaseModel):
    """Configuration for local vision-language model requests and pipeline parameters."""

    endpoint: str = Field(
        default="http://127.0.0.1:11434/v1",
        description="Local OpenAI-compatible API endpoint (Ollama, LM Studio, vLLM, etc.)",
    )
    model: str = Field(
        default="qwen2.5vl:3b",
        description="Local VLM model identifier",
    )
    api_key: Optional[str] = Field(
        default="",
        description="Optional API key for local gateway",
    )
    timeout_seconds: float = Field(
        default=60.0,
        ge=5.0,
        le=300.0,
        description="Request timeout in seconds",
    )
    mode: str = Field(
        default="virtual_address",
        description="Experiment mode: 'virtual_address' or 'direct_baseline'",
    )
    grid_rows: int = Field(
        default=8,
        ge=2,
        le=32,
        description="Number of virtual address rows per page",
    )
    grid_columns: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Number of virtual address columns per page",
    )
    neighbor_radius: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Candidate region neighbor expansion radius (0 = none, 1 = 8-neighbor)",
    )
    coarse_dpi: int = Field(
        default=100,
        ge=72,
        le=300,
        description="DPI for coarse whole-page rendering (100 DPI keeps vision tokens ~1200, fitting inside 4096 context)",
    )
    local_dpi: int = Field(
        default=250,
        ge=150,
        le=400,
        description="DPI for high-resolution candidate crops",
    )
    send_grid_overlay: bool = Field(
        default=True,
        description="Whether to overlay visible grid lines on the image sent to model (default True for VAQL)",
    )
    enable_local_refine: bool = Field(
        default=True,
        description="Whether to run local high-DPI refinement after coarse address localization",
    )
    num_ctx: int = Field(
        default=8192,
        ge=2048,
        le=32768,
        description="Context window length for local VLM (e.g. Ollama options.num_ctx to avoid context length exceeded)",
    )
    max_crop_pixels: int = Field(
        default=1800000,
        ge=500000,
        le=5000000,
        description="Maximum pixels for candidate crops before dynamic downscaling to prevent token explosion",
    )
    candidate_overlap_threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Overlap ratio threshold to flag LOCAL_VERIFY_REQUIRED",
    )
    exam_template: str = Field(
        default="kaoyan_math_16",
        description="Exam structure prior template: 'kaoyan_math_16', 'kaoyan_math_14', or 'general'",
    )
    full_width_layout: bool = Field(
        default=True,
        description="Whether to expand candidate rect to full page width (0.0~1.0) for single-column exam layouts",
    )
