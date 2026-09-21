"""Local Recognition (Experimental) with Virtual Address Question Localization (VAQL)."""

from .config import LocalVisionConfig
from .types import (
    VirtualRegion,
    CoarseQuestionOutput,
    CoarsePageOutput,
    LocalRefineOutput,
    CandidateRect,
    RefinedQuestionSegment,
    ExperimentMetrics,
    ExperimentRun,
    LocalRecognitionExperimentResult,
)
from .virtual_address import (
    parse_virtual_address,
    format_virtual_address,
    validate_virtual_address,
    get_neighbor_addresses,
)
from .page_table import VirtualPageTable
from .tiler import Tiler
from .provider import LocalVisionProvider, OpenAILocalVisionProvider
from .candidate_builder import CandidateBuilder
from .local_refiner import LocalRefiner
from .result_store import ResultStore
from .metrics import MetricsCalculator
from .service import LocalRecognitionExperimentService

__all__ = [
    "LocalVisionConfig",
    "VirtualRegion",
    "CoarseQuestionOutput",
    "CoarsePageOutput",
    "LocalRefineOutput",
    "CandidateRect",
    "RefinedQuestionSegment",
    "ExperimentMetrics",
    "ExperimentRun",
    "LocalRecognitionExperimentResult",
    "parse_virtual_address",
    "format_virtual_address",
    "validate_virtual_address",
    "get_neighbor_addresses",
    "VirtualPageTable",
    "Tiler",
    "LocalVisionProvider",
    "OpenAILocalVisionProvider",
    "CandidateBuilder",
    "LocalRefiner",
    "ResultStore",
    "MetricsCalculator",
    "LocalRecognitionExperimentService",
]
