"""Page domain model."""

from enum import Enum
from pydantic import BaseModel, Field
import uuid


class PageType(str, Enum):
    TEXT_PDF = "TEXT_PDF"
    IMAGE_PDF = "IMAGE_PDF"
    MIXED_PDF = "MIXED_PDF"


class PageInfo(BaseModel):
    """Metadata and dimensions of a PDF page."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    page_index: int = Field(ge=0)
    width: float = Field(gt=0, description="PDF page width in points")
    height: float = Field(gt=0, description="PDF page height in points")
    rotation: int = Field(default=0, description="Page rotation: 0, 90, 180, 270")
    page_type: PageType = PageType.MIXED_PDF
    thumbnail_path: str | None = None
