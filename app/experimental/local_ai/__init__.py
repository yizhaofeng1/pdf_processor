"""Local AI abstraction and provider layer for ExamSplit AI.

This module provides interfaces and implementations for local document layout analysis,
OCR/text extraction, and local VLM boundary verification.
"""

from .base import LocalLayoutProvider, LocalOCRProvider, LocalVLMProvider
from .config import LocalModelConfig
from .exceptions import (
    LocalAIError,
    LocalModelUnavailableError,
    LayoutModelError,
    OCRError,
    VLMError,
    LocalSchemaError,
    LocalCoordinateError,
)
from .types import (
    LayoutElement,
    OCRBlock,
    QuestionMarker,
    CandidateSegment,
    LocalQuestionCandidate,
    LocalBoundaryVerification,
    LocalPageAnalysis,
)

__all__ = [
    "LocalLayoutProvider",
    "LocalOCRProvider",
    "LocalVLMProvider",
    "LocalModelConfig",
    "LocalAIError",
    "LocalModelUnavailableError",
    "LayoutModelError",
    "OCRError",
    "VLMError",
    "LocalSchemaError",
    "LocalCoordinateError",
    "LayoutElement",
    "OCRBlock",
    "QuestionMarker",
    "CandidateSegment",
    "LocalQuestionCandidate",
    "LocalBoundaryVerification",
    "LocalPageAnalysis",
]
