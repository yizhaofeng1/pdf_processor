from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator
import uuid
from .segment import QuestionSegment


class QuestionType(str, Enum):
    """Question categorization."""
    SMALL = "小题"             # 小题（选择题、填空题等紧凑题型）
    LARGE = "大题"             # 大题（解答题、计算题、证明题等）
    CHOICE = "choice"          # 选择题（兼容）
    FILL_IN = "fill_in"        # 填空题（兼容）
    SOLVE = "solve"            # 解答题 / 计算题（兼容）
    PROOF = "proof"            # 证明题（兼容）
    OTHER = "other"            # 其他综合题


class QuestionStatus(str, Enum):
    """Lifecycle status of a question."""
    DETECTED = "DETECTED"
    VALIDATED = "VALIDATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    USER_CONFIRMED = "USER_CONFIRMED"
    USER_MODIFIED = "USER_MODIFIED"
    SELECTED = "SELECTED"
    EXPORTED = "EXPORTED"


class AnchorPoint(BaseModel):
    """Point anchor indicating question start or end."""
    page_index: int = Field(ge=0)
    normalized_point: tuple[float, float] = Field(..., description="(x, y) normalized coordinates")


class Question(BaseModel):
    """A logical question that may consist of one or more segments (e.g. cross-page)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    display_number: str = Field(..., description="E.g. '1', '17', 'Q5'")
    original_display_number: str | None = Field(default=None, description="Original question number before renumbering")
    question_type: QuestionType | str | None = None
    source_pdf_path: str | None = Field(default=None, description="Absolute path of the source exam PDF")
    source_paper_title: str | None = Field(default=None, description="Title of the source exam paper")
    segments: list[QuestionSegment] = Field(default_factory=list)
    start_anchor: AnchorPoint | None = None
    end_anchor: AnchorPoint | None = None
    continuation: bool = Field(default=False, description="Whether this question spans multiple pages")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    review_required: bool = False
    selected: bool = True
    sort_order: int = 0
    user_modified: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    status: QuestionStatus = QuestionStatus.DETECTED

    @field_validator("source_pdf_path", mode="before")
    @classmethod
    def _coerce_source_pdf_path(cls, v: Any) -> str | None:
        if v is None:
            return None
        return str(v)

    def is_small_question(self) -> bool:
        """Check if this is a small question (choice, fill-in, or compact)."""
        t = self.question_type.value if hasattr(self.question_type, "value") else str(self.question_type or "")
        return t in ("小题", "choice", "fill_in", "选择题", "填空题")

    def is_large_question(self) -> bool:
        """Check if this is a large question (solve, proof, essay, or large)."""
        t = self.question_type.value if hasattr(self.question_type, "value") else str(self.question_type or "")
        return t in ("大题", "solve", "proof", "other", "解答题", "证明题", "计算题", "综合题")

    def get_type_display_name(self) -> str:
        """Get standard human-friendly Chinese question type label."""
        if self.is_small_question():
            t = self.question_type.value if hasattr(self.question_type, "value") else str(self.question_type or "")
            if t in ("choice", "选择题"):
                return "选择题"
            elif t in ("fill_in", "填空题"):
                return "填空题"
            return "小题"
        elif self.is_large_question():
            t = self.question_type.value if hasattr(self.question_type, "value") else str(self.question_type or "")
            if t in ("solve", "解答题"):
                return "解答题"
            elif t in ("proof", "证明题"):
                return "证明题"
            return "大题"
        return "试题"
