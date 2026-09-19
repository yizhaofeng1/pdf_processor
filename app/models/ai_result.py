"""AI Provider Request and Response models."""

from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone
from .question import Question
from .document import DocumentMetadata


class VisionAnalysisRequest(BaseModel):
    """Payload sent to VisionModelProvider."""
    page_indices: list[int]
    image_paths: list[str]
    pdf_path: str
    prompt_version: str = "v1"
    context_hints: dict[str, str] = Field(default_factory=dict)


class VisionAnalysisResult(BaseModel):
    """Structured response parsed from AI Provider."""
    schema_version: str = "1.0"
    document: DocumentMetadata = Field(default_factory=DocumentMetadata)
    questions: list[Question] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_response: str = ""
    cost_tokens: int | None = None


class AIRunRecord(BaseModel):
    """Execution log of an AI API call."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    provider: str
    model: str
    prompt_hash: str = ""
    input_hash: str = ""
    raw_response_path: str = ""
    status: str = "SUCCESS"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
