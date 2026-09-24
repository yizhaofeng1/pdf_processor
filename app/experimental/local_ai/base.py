"""Abstract provider interfaces for local AI components.

Defines the contract for layout detection, text extraction/OCR, and local VLM verification.
Allows swappable implementations (e.g. PP-DocLayoutV3 vs Native PyMuPDF Layout,
PaddleOCR vs Native Text extraction, Ollama vs llama-server).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from .types import LayoutElement, OCRBlock, LocalQuestionCandidate, LocalBoundaryVerification


class LocalLayoutProvider(ABC):
    """Abstract interface for document layout analysis."""

    @abstractmethod
    def analyze_page(
        self,
        page_image_path: Optional[str],
        page_index: int,
        pdf_page: Any = None,
    ) -> List[LayoutElement]:
        """Analyze page layout to extract categorized bounding elements.
        
        Args:
            page_image_path: Path to rendered page image (if available/required).
            page_index: 0-indexed page number.
            pdf_page: PyMuPDF Page object for native extraction (if available).
            
        Returns:
            List of LayoutElement with normalized bboxes and standard categories.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend dependencies or models are available."""
        pass


class LocalOCRProvider(ABC):
    """Abstract interface for local text extraction and OCR."""

    @abstractmethod
    def extract_text_blocks(
        self,
        page_image_path: Optional[str],
        page_index: int,
        pdf_page: Any = None,
    ) -> List[OCRBlock]:
        """Extract text blocks with bounding boxes and source attribution.
        
        Args:
            page_image_path: Path to rendered page image.
            page_index: 0-indexed page number.
            pdf_page: PyMuPDF Page object for native vector text.
            
        Returns:
            List of OCRBlock with normalized bboxes and extracted text.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if OCR backend is available."""
        pass


class LocalVLMProvider(ABC):
    """Abstract interface for local vision-language model boundary verification."""

    @abstractmethod
    def verify_question_region(
        self,
        crop_image_b64: str,
        candidate: LocalQuestionCandidate,
        context: Optional[Dict[str, Any]] = None,
    ) -> LocalBoundaryVerification:
        """Verify candidate question region and suggest boundary adjustments if needed.
        
        Args:
            crop_image_b64: Base64 data string (JPEG/PNG) of the cropped candidate region.
            candidate: Current LocalQuestionCandidate to verify.
            context: Additional context (neighboring markers, page size, etc.).
            
        Returns:
            LocalBoundaryVerification with acceptance decision, reason codes, and optional bbox.
        """
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """Check if the local VLM server/endpoint is reachable and responsive."""
        pass
