"""Domain models and Pydantic schemas for the Local Recognition (VAQL) experiment."""

from typing import Optional, List, Tuple, Dict, Any
from pydantic import BaseModel, Field, field_validator
import uuid
from datetime import datetime, timezone


class VirtualRegion(BaseModel):
    """Represents a discrete grid cell in the Virtual Document Space."""
    page_index: int = Field(ge=0, description="0-indexed page index")
    row: int = Field(ge=0, description="0-indexed row index")
    col: int = Field(ge=0, description="0-indexed column index")
    address: str = Field(..., description="String address, e.g. 'P03:R05:C02'")
    normalized_rect: Tuple[float, float, float, float] = Field(
        ..., description="(x1, y1, x2, y2) in [0.0, 1.0]"
    )
    pdf_rect: Tuple[float, float, float, float] = Field(
        ..., description="(x0, y0, x1, y1) in PDF points"
    )


class CoarseQuestionOutput(BaseModel):
    """Parsed output for a question from the coarse address stage."""
    question_number: str = Field(..., description="E.g. '1', '17', 'Q5'")
    regions: List[str] = Field(..., description="List of virtual addresses, e.g. ['P03:R04:C00']")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    cross_page: bool = Field(default=False, description="Whether question might continue to next page")


class CoarsePageOutput(BaseModel):
    """Coarse localization response schema for a single page."""
    schema_version: str = Field(default="vaql-coarse-v1")
    page_index: int = Field(ge=0)
    questions: List[CoarseQuestionOutput] = Field(default_factory=list)


class LocalRefineOutput(BaseModel):
    """Refined local bounding box within a candidate crop."""
    schema_version: str = Field(default="vaql-local-v1")
    question_number: str
    bbox: Tuple[float, float, float, float] = Field(
        ..., description="Local normalized bbox [x1, y1, x2, y2] relative to candidate crop [0.0, 1.0]"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    boundary_complete: bool = Field(default=True, description="Whether the entire question is enclosed")
    needs_neighbor: bool = Field(default=False, description="Whether boundary was cut off by crop edge")

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        x1, y1, x2, y2 = v
        x1 = max(0.0, min(1.0, float(x1)))
        y1 = max(0.0, min(1.0, float(y1)))
        x2 = max(0.0, min(1.0, float(x2)))
        y2 = max(0.0, min(1.0, float(y2)))
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        return (x1, y1, x2, y2)


class CandidateRect(BaseModel):
    """Merged local region candidate for a specific question on a page."""
    question_number: str
    page_index: int = Field(ge=0)
    source_regions: List[str] = Field(default_factory=list)
    normalized_rect: Tuple[float, float, float, float] = Field(
        ..., description="(x1, y1, x2, y2) on page [0.0, 1.0]"
    )
    pdf_rect: Tuple[float, float, float, float] = Field(
        ..., description="(x0, y0, x1, y1) in PDF points"
    )
    expanded: bool = False
    overlap_detected: bool = False
    verify_required: bool = False


class RefinedQuestionSegment(BaseModel):
    """Final calculated question segment for the experiment."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_number: str
    page_index: int = Field(ge=0)
    normalized_bbox: Tuple[float, float, float, float] = Field(
        ..., description="Full-page normalized bbox (x1, y1, x2, y2) in [0.0, 1.0]"
    )
    pdf_bbox: Tuple[float, float, float, float] = Field(
        ..., description="PDF coordinates (x0, y0, x1, y1) in points"
    )
    confidence: float = 1.0
    boundary_complete: bool = True
    source: str = "local_experiment"
    candidate_rect: Optional[CandidateRect] = None


class ExperimentMetrics(BaseModel):
    """Evaluation and benchmark metrics for an experiment run."""
    total_questions_detected: int = 0
    question_precision: Optional[float] = None
    question_recall: Optional[float] = None
    mean_boundary_iou: Optional[float] = None
    cross_page_count: int = 0
    cross_page_accuracy: Optional[float] = None
    missed_question_count: int = 0
    duplicate_question_count: int = 0
    over_crop_count: int = 0
    under_crop_count: int = 0
    coarse_calls: int = 0
    local_calls: int = 0
    total_calls: int = 0
    latency_seconds: float = 0.0
    estimated_tokens: Optional[int] = None
    input_image_count: int = 0
    input_image_pixels: int = 0


class ExperimentRun(BaseModel):
    """Metadata tracking a single experimental run."""
    run_id: str = Field(default_factory=lambda: f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}")
    source_pdf_hash: str = ""
    source_pdf_name: str = ""
    model_provider: str = "local"
    model_name: str = "qwen2.5-vl"
    model_parameter_scale: Optional[str] = None
    mode: str = "virtual_address"  # "virtual_address" or "direct_baseline"
    grid_rows: int = 8
    grid_columns: int = 4
    neighbor_radius: int = 1
    coarse_dpi: int = 100
    local_dpi: int = 250
    prompt_version: str = "v1"
    start_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = None
    status: str = "PENDING"  # "PENDING", "RUNNING", "SUCCESS", "FAILED"
    error_message: Optional[str] = None


class LocalRecognitionExperimentResult(BaseModel):
    """Full aggregated output of a local recognition experiment."""
    run: ExperimentRun
    coarse_results: List[CoarsePageOutput] = Field(default_factory=list)
    candidates: List[CandidateRect] = Field(default_factory=list)
    segments: List[RefinedQuestionSegment] = Field(default_factory=list)
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)
    raw_model_outputs: List[Dict[str, Any]] = Field(default_factory=list)
