"""Document and Project domain models."""

from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone


class DocumentMetadata(BaseModel):
    """Extracted or inferred metadata of an exam document."""
    title: str = ""
    subject: str = ""
    year: int | None = None
    page_count: int = 0


class Project(BaseModel):
    """Top-level project representing an exam splitting workspace."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    source_pdf: str
    source_hash: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
