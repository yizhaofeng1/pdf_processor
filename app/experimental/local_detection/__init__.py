"""Local heuristic detection, reading order, and boundary resolution pipeline.

Implements the deterministic geometry and heuristic layers defined in
ExamSplitAI_LocalSmallModel_Mainstream_Implementation_Spec.md:
- Reading Order & Column Detection
- Question Marker Detection & False-Positive Filtering
- Question Candidate Assembly
- Boundary Resolution (Padding, Option Containment, White-space Trimming)
- Confidence Evaluation & VLM Routing
- Cross-Page Question Analysis
"""

from .reading_order import ReadingOrderDetector, sort_elements_reading_order
from .marker_detector import LocalMarkerDetector
from .candidate_builder import LocalCandidateBuilder
from .boundary_resolver import LocalBoundaryResolver
from .confidence_router import LocalConfidenceRouter
from .cross_page import LocalCrossPageResolver

__all__ = [
    "ReadingOrderDetector",
    "sort_elements_reading_order",
    "LocalMarkerDetector",
    "LocalCandidateBuilder",
    "LocalBoundaryResolver",
    "LocalConfidenceRouter",
    "LocalCrossPageResolver",
]
