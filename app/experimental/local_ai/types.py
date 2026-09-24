"""Data models and schemas for the local AI pipeline.

Implements data structures defined in ExamSplitAI_LocalSmallModel_Mainstream_Implementation_Spec.md:
- LayoutElement: standard document layout block (text, formula, image, title, etc.)
- OCRBlock: unified text block with normalized coordinates and source attribution
- QuestionMarker: detected question numbering anchor
- LocalQuestionCandidate: assembled candidate question region
- LocalBoundaryVerification: Pydantic schema for local VLM verification output
- LocalPageAnalysis: aggregated per-page parsing output
"""

from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator


class LayoutElement(BaseModel):
    """Unified layout element from PP-DocLayoutV3 or native heuristic layout."""
    page_index: int
    category: str  # text, title, formula, image, table, figure, header, footer, page_number
    bbox: Tuple[float, float, float, float]  # Normalized (x1, y1, x2, y2) in 0.0 ~ 1.0
    confidence: float = 1.0
    order_hint: Optional[int] = None
    text: str = ""

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        x1, y1, x2, y2 = v
        # Clamp to 0.0 ~ 1.0
        x1 = max(0.0, min(1.0, float(x1)))
        y1 = max(0.0, min(1.0, float(y1)))
        x2 = max(0.0, min(1.0, float(x2)))
        y2 = max(0.0, min(1.0, float(y2)))
        if x2 <= x1:
            x2 = min(1.0, x1 + 0.001)
        if y2 <= y1:
            y2 = min(1.0, y1 + 0.001)
        return (round(x1, 5), round(y1, 5), round(x2, 5), round(y2, 5))


class OCRBlock(BaseModel):
    """Unified text block from native PDF text extraction or local OCR."""
    text: str
    bbox: Tuple[float, float, float, float]  # Normalized (x1, y1, x2, y2)
    confidence: float = 1.0
    page_index: int
    source: str = "native_pdf"  # "native_pdf" or "ocr"

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        x1, y1, x2, y2 = v
        x1 = max(0.0, min(1.0, float(x1)))
        y1 = max(0.0, min(1.0, float(y1)))
        x2 = max(0.0, min(1.0, float(x2)))
        y2 = max(0.0, min(1.0, float(y2)))
        if x2 <= x1:
            x2 = min(1.0, x1 + 0.001)
        if y2 <= y1:
            y2 = min(1.0, y1 + 0.001)
        return (round(x1, 5), round(y1, 5), round(x2, 5), round(y2, 5))


class QuestionMarker(BaseModel):
    """Detected question numbering marker."""
    number: str  # e.g., "1", "2", "17", "一"
    page_index: int
    bbox: Tuple[float, float, float, float]  # Normalized (x1, y1, x2, y2)
    confidence: float = 1.0
    source: str = "native"  # "native", "ocr", "layout", "vlm"
    raw_text: str = ""
    is_section_header: bool = False


class CandidateSegment(BaseModel):
    """Bounding segment of a question candidate on a specific page."""
    page_index: int
    bbox: Tuple[float, float, float, float]  # Normalized (x1, y1, x2, y2)
    layout_element_ids: List[int] = Field(default_factory=list)
    text_snippet: str = ""


class LocalBoundaryVerification(BaseModel):
    """Strict schema for local VLM verification response."""
    schema_version: str = "1.0"
    question_number: str
    accept: bool
    bbox: Optional[Tuple[float, float, float, float]] = None
    cross_page: bool = False
    contains_all_required_content: bool = True
    needs_expand_up: bool = False
    needs_expand_down: bool = False
    confidence: float = 1.0
    reason_codes: List[str] = Field(default_factory=list)

    @field_validator("bbox")
    @classmethod
    def validate_vlm_bbox(cls, v: Optional[Tuple[float, float, float, float]]) -> Optional[Tuple[float, float, float, float]]:
        if v is None:
            return None
        x1, y1, x2, y2 = v
        x1 = max(0.0, min(1.0, float(x1)))
        y1 = max(0.0, min(1.0, float(y1)))
        x2 = max(0.0, min(1.0, float(x2)))
        y2 = max(0.0, min(1.0, float(y2)))
        if x2 <= x1:
            x2 = min(1.0, x1 + 0.001)
        if y2 <= y1:
            y2 = min(1.0, y1 + 0.001)
        return (round(x1, 5), round(y1, 5), round(x2, 5), round(y2, 5))


class LocalQuestionCandidate(BaseModel):
    """Assembled question candidate from markers, layout elements, and boundaries."""
    question_number: str
    segments: List[CandidateSegment] = Field(default_factory=list)
    confidence: float = 1.0
    reasons: List[str] = Field(default_factory=list)
    has_options: bool = False
    options_found: List[str] = Field(default_factory=list)
    question_type: str = "unknown"  # "choice", "fill_blank", "solution"
    needs_vlm: bool = False
    vlm_verification: Optional[LocalBoundaryVerification] = None


class LocalPageAnalysis(BaseModel):
    """Aggregate analysis result for a single page."""
    page_index: int
    layout_elements: List[LayoutElement] = Field(default_factory=list)
    text_blocks: List[OCRBlock] = Field(default_factory=list)
    markers: List[QuestionMarker] = Field(default_factory=list)
    is_two_column: bool = False
    column_split_x: Optional[float] = None
