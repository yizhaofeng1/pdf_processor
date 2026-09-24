"""Experimental modules for ExamSplit AI.

Contains isolated implementations of local small-model exam segmentation
based on ExamSplitAI_LocalSmallModel_Mainstream_Implementation_Spec.md.
"""

from .local_recognition.service import LocalAnalysisService
from .local_recognition.ui import LocalRecognitionExperimentDialog

__all__ = [
    "LocalAnalysisService",
    "LocalRecognitionExperimentDialog",
]
