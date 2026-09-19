"""PDF processing, rendering and coordinate mapping package."""

from .reader import PDFReader, validate_pdf, PDFValidationResult, compute_file_hash
from .renderer import PDFRenderer, pixmap_to_qimage, pixmap_to_qpixmap
from .coordinate import (
    normalized_to_pdf_rect,
    pdf_rect_to_normalized,
    normalized_to_image_rect,
    image_rect_to_normalized,
    add_padding,
    calculate_iou,
    calculate_overlap_ratio,
    merge_bboxes,
)

__all__ = [
    "PDFReader",
    "validate_pdf",
    "PDFValidationResult",
    "compute_file_hash",
    "PDFRenderer",
    "pixmap_to_qimage",
    "pixmap_to_qpixmap",
    "normalized_to_pdf_rect",
    "pdf_rect_to_normalized",
    "normalized_to_image_rect",
    "image_rect_to_normalized",
    "add_padding",
    "calculate_iou",
    "calculate_overlap_ratio",
    "merge_bboxes",
]
