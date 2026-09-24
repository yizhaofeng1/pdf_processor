"""Categorized exceptions for the local AI pipeline.

Ensures clear separation of error types and prevents exceptions from propagating
unhandled into the main cloud pipeline or GUI event loop.
"""


class LocalAIError(Exception):
    """Base exception for all local AI and detection errors."""
    pass


class LocalModelUnavailableError(LocalAIError):
    """Raised when a configured local model or service endpoint is unreachable."""
    pass


class LayoutModelError(LocalAIError):
    """Raised when layout detection fails to process an image."""
    pass


class OCRError(LocalAIError):
    """Raised when OCR recognition fails on a page or region."""
    pass


class VLMError(LocalAIError):
    """Raised when the local vision-language model fails to generate or return a response."""
    pass


class LocalSchemaError(LocalAIError):
    """Raised when local model output fails schema validation."""
    pass


class LocalCoordinateError(LocalAIError):
    """Raised when coordinate normalization or transformation produces invalid bounds."""
    pass


class LocalPipelineError(LocalAIError):
    """Raised when the orchestrating pipeline encounters an unrecoverable state."""
    pass
