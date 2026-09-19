"""QuestionSegment domain model."""

from pydantic import BaseModel, Field, field_validator
import uuid


class QuestionSegment(BaseModel):
    """Represents a bounded visual region of a question on a specific page."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_id: str = ""
    page_index: int = Field(ge=0, description="0-indexed page number")
    normalized_bbox: tuple[float, float, float, float] = Field(
        ...,
        description="Normalized coordinates (x1, y1, x2, y2) in range [0.0, 1.0]",
    )
    pdf_bbox: tuple[float, float, float, float] | None = Field(
        default=None,
        description="PDF points rect (x0, y0, x1, y1) calculated by coordinate engine",
    )
    user_modified: bool = Field(default=False, description="Whether modified by user")

    @field_validator("normalized_bbox")
    @classmethod
    def validate_normalized_bbox(cls, v: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = v
        for val in (x1, y1, x2, y2):
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"Normalized coordinate must be between 0.0 and 1.0, got: {val}")
        if x1 >= x2:
            raise ValueError(f"Invalid bounding box: x1 ({x1}) must be less than x2 ({x2})")
        if y1 >= y2:
            raise ValueError(f"Invalid bounding box: y1 ({y1}) must be less than y2 ({y2})")
        return v
