"""Local exam recognition experiment module.

Exposes LocalAnalysisService and LocalRecognitionExperimentDialog.
"""

from .service import LocalAnalysisService
from .ui import LocalRecognitionExperimentDialog

__all__ = [
    "LocalAnalysisService",
    "LocalRecognitionExperimentDialog",
]
