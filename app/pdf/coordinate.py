"""Coordinate transformations, safety padding and bounding box geometry engine.

Distinguishes between:
A. AI Normalized Coordinates: (0.0 ~ 1.0)
B. Rendered Image Coordinates: (pixels)
C. PDF Coordinates: (points, top-left origin)
"""

from typing import Union
import pymupdf

NormalizedBBox = tuple[float, float, float, float]
PDFRectTuple = tuple[float, float, float, float]
ImageRectTuple = tuple[int, int, int, int]


def clamp(val: float, min_val: float, max_val: float) -> float:
    """Clamp value between min_val and max_val."""
    return max(min_val, min(max_val, val))


def get_dimensions(
    page_or_rect: Union[pymupdf.Page, pymupdf.Rect, PDFRectTuple],
) -> tuple[float, float]:
    """Extract (width, height) in PDF points."""
    if isinstance(page_or_rect, pymupdf.Page):
        rect = page_or_rect.rect
        return (rect.width, rect.height)
    elif isinstance(page_or_rect, pymupdf.Rect):
        return (page_or_rect.width, page_or_rect.height)
    else:
        x0, y0, x1, y1 = page_or_rect
        return (abs(x1 - x0), abs(y1 - y0))


def add_padding(
    rect: pymupdf.Rect,
    boundary: pymupdf.Rect,
    pad_x: float,
    pad_y: float,
) -> pymupdf.Rect:
    """Safely expand rect by pad_x, pad_y while constraining within boundary."""
    x0 = max(boundary.x0, rect.x0 - pad_x)
    y0 = max(boundary.y0, rect.y0 - pad_y)
    x1 = min(boundary.x1, rect.x1 + pad_x)
    y1 = min(boundary.y1, rect.y1 + pad_y)
    return pymupdf.Rect(x0, y0, x1, y1)


def normalized_to_pdf_rect(
    page_or_rect: Union[pymupdf.Page, pymupdf.Rect, PDFRectTuple],
    normalized_bbox: NormalizedBBox,
    padding_ratio: tuple[float, float] = (0.005, 0.004),
) -> pymupdf.Rect:
    """Convert AI normalized bbox [0, 1] to PyMuPDF Rect with safety padding.

    Args:
        page_or_rect: PyMuPDF Page, Rect, or (x0, y0, x1, y1)
        normalized_bbox: (nx1, ny1, nx2, ny2) in [0.0, 1.0]
        padding_ratio: (horizontal_ratio, vertical_ratio)

    Returns:
        pymupdf.Rect in PDF points.
    """
    if isinstance(page_or_rect, pymupdf.Page):
        base_rect = page_or_rect.rect
    elif isinstance(page_or_rect, pymupdf.Rect):
        base_rect = page_or_rect
    else:
        base_rect = pymupdf.Rect(*page_or_rect)

    nx1, ny1, nx2, ny2 = normalized_bbox
    nx1 = clamp(nx1, 0.0, 1.0)
    ny1 = clamp(ny1, 0.0, 1.0)
    nx2 = clamp(nx2, 0.0, 1.0)
    ny2 = clamp(ny2, 0.0, 1.0)

    if nx1 > nx2:
        nx1, nx2 = nx2, nx1
    if ny1 > ny2:
        ny1, ny2 = ny2, ny1

    width = base_rect.width
    height = base_rect.height

    raw_x0 = base_rect.x0 + nx1 * width
    raw_y0 = base_rect.y0 + ny1 * height
    raw_x1 = base_rect.x0 + nx2 * width
    raw_y1 = base_rect.y0 + ny2 * height

    rect = pymupdf.Rect(raw_x0, raw_y0, raw_x1, raw_y1)

    pad_x = width * padding_ratio[0]
    pad_y = height * padding_ratio[1]

    return add_padding(rect, base_rect, pad_x, pad_y)


def pdf_rect_to_normalized(
    page_or_rect: Union[pymupdf.Page, pymupdf.Rect, PDFRectTuple],
    pdf_rect: Union[pymupdf.Rect, PDFRectTuple],
) -> NormalizedBBox:
    """Convert a PDF points rect to normalized [0.0, 1.0] coordinates."""
    if isinstance(page_or_rect, pymupdf.Page):
        base_rect = page_or_rect.rect
    elif isinstance(page_or_rect, pymupdf.Rect):
        base_rect = page_or_rect
    else:
        base_rect = pymupdf.Rect(*page_or_rect)

    if not isinstance(pdf_rect, pymupdf.Rect):
        pdf_rect = pymupdf.Rect(*pdf_rect)

    width = base_rect.width
    height = base_rect.height

    if width <= 0 or height <= 0:
        return (0.0, 0.0, 1.0, 1.0)

    nx1 = clamp((pdf_rect.x0 - base_rect.x0) / width, 0.0, 1.0)
    ny1 = clamp((pdf_rect.y0 - base_rect.y0) / height, 0.0, 1.0)
    nx2 = clamp((pdf_rect.x1 - base_rect.x0) / width, 0.0, 1.0)
    ny2 = clamp((pdf_rect.y1 - base_rect.y0) / height, 0.0, 1.0)

    return (nx1, ny1, nx2, ny2)


def normalized_to_image_rect(
    image_width: int,
    image_height: int,
    normalized_bbox: NormalizedBBox,
) -> ImageRectTuple:
    """Convert normalized bbox to pixel coordinates."""
    nx1, ny1, nx2, ny2 = normalized_bbox
    px1 = int(round(clamp(nx1, 0.0, 1.0) * image_width))
    py1 = int(round(clamp(ny1, 0.0, 1.0) * image_height))
    px2 = int(round(clamp(nx2, 0.0, 1.0) * image_width))
    py2 = int(round(clamp(ny2, 0.0, 1.0) * image_height))
    return (px1, py1, px2, py2)


def image_rect_to_normalized(
    image_width: int,
    image_height: int,
    image_rect: ImageRectTuple,
) -> NormalizedBBox:
    """Convert pixel coordinates to normalized bbox."""
    if image_width <= 0 or image_height <= 0:
        return (0.0, 0.0, 1.0, 1.0)

    px1, py1, px2, py2 = image_rect
    nx1 = clamp(px1 / image_width, 0.0, 1.0)
    ny1 = clamp(py1 / image_height, 0.0, 1.0)
    nx2 = clamp(px2 / image_width, 0.0, 1.0)
    ny2 = clamp(py2 / image_height, 0.0, 1.0)
    return (nx1, ny1, nx2, ny2)


def calculate_iou(
    bbox_a: NormalizedBBox,
    bbox_b: NormalizedBBox,
) -> float:
    """Calculate Intersection over Union (IoU) between two bounding boxes."""
    ax1, ay1, ax2, ay2 = bbox_a
    bx1, by1, bx2, by2 = bbox_b

    # Intersection coordinates
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

    union = area_a + area_b - intersection
    if union <= 0.0:
        return 0.0

    return intersection / union


def calculate_overlap_ratio(
    bbox_a: NormalizedBBox,
    bbox_b: NormalizedBBox,
) -> float:
    """Calculate overlap ratio relative to the smaller bounding box area."""
    ax1, ay1, ax2, ay2 = bbox_a
    bx1, by1, bx2, by2 = bbox_b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

    min_area = min(area_a, area_b)
    if min_area <= 0.0:
        return 0.0

    return intersection / min_area


def merge_bboxes(bboxes: list[NormalizedBBox]) -> NormalizedBBox:
    """Calculate the minimal bounding box enclosing all input bboxes."""
    if not bboxes:
        return (0.0, 0.0, 1.0, 1.0)

    min_x = min(b[0] for b in bboxes)
    min_y = min(b[1] for b in bboxes)
    max_x = max(b[2] for b in bboxes)
    max_y = max(b[3] for b in bboxes)

    return (clamp(min_x, 0.0, 1.0), clamp(min_y, 0.0, 1.0), clamp(max_x, 0.0, 1.0), clamp(max_y, 0.0, 1.0))
