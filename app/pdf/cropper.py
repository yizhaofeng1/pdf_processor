"""PDF Cropper: Geometric calculations and clipping rect helpers for lossless PDF extraction.

Follows the Core Principle:
- Never regenerate PDF from OCR text.
- Extracts native vector/raster streams directly using PyMuPDF clip regions.
"""

from typing import Tuple, Union
import pymupdf

# ISO 216 standard A4 dimensions in PDF points (72 points = 1 inch, 210 x 297 mm)
A4_WIDTH: float = 595.32
A4_HEIGHT: float = 841.92

# Default margins (0.5 inch / ~12.7 mm = 36 pt)
DEFAULT_MARGIN: float = 36.0


def calculate_fit_rect(
    source_rect: Union[pymupdf.Rect, Tuple[float, float, float, float]],
    target_bounds: Union[pymupdf.Rect, Tuple[float, float, float, float]],
    max_scale: float = 1.0,
    align: str = "center",  # "center", "left", "top"
) -> pymupdf.Rect:
    """Calculate target placement Rect preserving aspect ratio.

    Args:
        source_rect: Original bounding box of the segment (x0, y0, x1, y1)
        target_bounds: Available area on target page (x0, y0, x1, y1)
        max_scale: Maximum magnification factor (default 1.0 to preserve native 1:1 crispness)
        align: Horizontal alignment within available target bounds ("center" or "left")

    Returns:
        pymupdf.Rect representing the destination box on the output page.
    """
    s_rect = source_rect if isinstance(source_rect, pymupdf.Rect) else pymupdf.Rect(*source_rect)
    t_rect = target_bounds if isinstance(target_bounds, pymupdf.Rect) else pymupdf.Rect(*target_bounds)

    s_w = max(1.0, s_rect.width)
    s_h = max(1.0, s_rect.height)
    t_w = max(1.0, t_rect.width)
    t_h = max(1.0, t_rect.height)

    # Scale factor: shrink if larger than target bounds; clamp to max_scale
    scale_w = t_w / s_w
    scale_h = t_h / s_h
    scale = min(scale_w, scale_h, max_scale)

    dest_w = s_w * scale
    dest_h = s_h * scale

    # Calculate top-left point
    if align == "left":
        dest_x = t_rect.x0
    else:
        # Centered horizontally
        dest_x = t_rect.x0 + (t_w - dest_w) / 2.0

    # Start at top of target bounds
    dest_y = t_rect.y0

    return pymupdf.Rect(dest_x, dest_y, dest_x + dest_w, dest_y + dest_h)
