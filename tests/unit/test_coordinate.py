"""Unit tests for coordinate transformations, bounding boxes, and padding."""

import pytest
from pathlib import Path
import pymupdf

from app.pdf.coordinate import (
    normalized_to_pdf_rect,
    pdf_rect_to_normalized,
    normalized_to_image_rect,
    image_rect_to_normalized,
    add_padding,
    calculate_iou,
    calculate_overlap_ratio,
    merge_bboxes,
    clamp,
)
from app.pdf.reader import PDFReader

TEST_PDF = Path(__file__).resolve().parent.parent.parent / "2010_math_test.pdf"


def test_clamp():
    """Verify clamp utility."""
    assert clamp(0.5, 0.0, 1.0) == 0.5
    assert clamp(-0.2, 0.0, 1.0) == 0.0
    assert clamp(1.4, 0.0, 1.0) == 1.0


def test_normalized_to_pdf_rect_no_padding():
    """Verify normalized [0.1, 0.2, 0.9, 0.6] on a 1000x2000 page without padding."""
    page_rect = pymupdf.Rect(0, 0, 1000, 2000)
    pdf_rect = normalized_to_pdf_rect(
        page_rect,
        (0.1, 0.2, 0.9, 0.6),
        padding_ratio=(0.0, 0.0),
    )
    assert pdf_rect.x0 == pytest.approx(100.0)
    assert pdf_rect.y0 == pytest.approx(400.0)
    assert pdf_rect.x1 == pytest.approx(900.0)
    assert pdf_rect.y1 == pytest.approx(1200.0)


def test_normalized_to_pdf_rect_with_safety_padding():
    """Verify safety padding expands rectangle properly."""
    page_rect = pymupdf.Rect(0, 0, 1000, 1000)
    # horizontal padding 1% = 10pt, vertical padding 2% = 20pt
    pdf_rect = normalized_to_pdf_rect(
        page_rect,
        (0.2, 0.3, 0.8, 0.7),
        padding_ratio=(0.01, 0.02),
    )
    assert pdf_rect.x0 == pytest.approx(190.0)
    assert pdf_rect.y0 == pytest.approx(280.0)
    assert pdf_rect.x1 == pytest.approx(810.0)
    assert pdf_rect.y1 == pytest.approx(720.0)


def test_padding_does_not_exceed_page_boundaries():
    """Verify padding is clamped to page rect."""
    page_rect = pymupdf.Rect(0, 0, 1000, 1000)
    # A box touching the edge
    pdf_rect = normalized_to_pdf_rect(
        page_rect,
        (0.0, 0.0, 1.0, 1.0),
        padding_ratio=(0.05, 0.05),
    )
    assert pdf_rect.x0 == 0.0
    assert pdf_rect.y0 == 0.0
    assert pdf_rect.x1 == 1000.0
    assert pdf_rect.y1 == 1000.0


def test_pdf_rect_to_normalized_roundtrip():
    """Verify converting back and forth yields the original normalized coordinates."""
    page_rect = pymupdf.Rect(0, 0, 600, 800)
    orig_norm = (0.15, 0.25, 0.85, 0.75)

    pdf_rect = normalized_to_pdf_rect(page_rect, orig_norm, padding_ratio=(0.0, 0.0))
    recovered_norm = pdf_rect_to_normalized(page_rect, pdf_rect)

    assert recovered_norm[0] == pytest.approx(orig_norm[0])
    assert recovered_norm[1] == pytest.approx(orig_norm[1])
    assert recovered_norm[2] == pytest.approx(orig_norm[2])
    assert recovered_norm[3] == pytest.approx(orig_norm[3])


def test_image_rect_transformations():
    """Verify pixel coordinates to normalized and back."""
    img_w, img_h = 2000, 3000
    norm_bbox = (0.1, 0.2, 0.9, 0.8)

    px_rect = normalized_to_image_rect(img_w, img_h, norm_bbox)
    assert px_rect == (200, 600, 1800, 2400)

    recovered = image_rect_to_normalized(img_w, img_h, px_rect)
    assert recovered[0] == pytest.approx(0.1)
    assert recovered[1] == pytest.approx(0.2)
    assert recovered[2] == pytest.approx(0.9)
    assert recovered[3] == pytest.approx(0.8)


def test_inverted_coordinates_handling():
    """Verify x1 > x2 or y1 > y2 are safely ordered."""
    page_rect = pymupdf.Rect(0, 0, 1000, 1000)
    # Passed in inverted order
    pdf_rect = normalized_to_pdf_rect(
        page_rect,
        (0.9, 0.8, 0.1, 0.2),
        padding_ratio=(0.0, 0.0),
    )
    assert pdf_rect.x0 == pytest.approx(100.0)
    assert pdf_rect.y0 == pytest.approx(200.0)
    assert pdf_rect.x1 == pytest.approx(900.0)
    assert pdf_rect.y1 == pytest.approx(800.0)


def test_calculate_iou():
    """Verify Intersection over Union computation."""
    # 1. Identical boxes -> IoU = 1.0
    b1 = (0.1, 0.1, 0.5, 0.5)
    assert calculate_iou(b1, b1) == pytest.approx(1.0)

    # 2. Non-overlapping boxes -> IoU = 0.0
    b2 = (0.6, 0.6, 0.9, 0.9)
    assert calculate_iou(b1, b2) == pytest.approx(0.0)

    # 3. Partial overlap
    # box a: [0, 0, 2, 2] -> area = 4
    # box b: [1, 0, 3, 2] -> area = 4
    # intersection: [1, 0, 2, 2] -> area = 2
    # union: 4 + 4 - 2 = 6 -> IoU = 2/6 = 1/3
    ba = (0.0, 0.0, 0.2, 0.2)
    bb = (0.1, 0.0, 0.3, 0.2)
    assert calculate_iou(ba, bb) == pytest.approx(1.0 / 3.0)


def test_calculate_overlap_ratio():
    """Verify overlap ratio relative to smaller box."""
    # Box A inside Box B
    small = (0.2, 0.2, 0.4, 0.4)
    large = (0.1, 0.1, 0.8, 0.8)
    assert calculate_overlap_ratio(small, large) == pytest.approx(1.0)


def test_merge_bboxes():
    """Verify merging multiple bounding boxes."""
    b1 = (0.1, 0.2, 0.4, 0.5)
    b2 = (0.3, 0.1, 0.8, 0.6)
    merged = merge_bboxes([b1, b2])
    assert merged == (0.1, 0.1, 0.8, 0.6)


def test_real_pdf_page_coordinates():
    """Verify real PDF page coordinate calculation."""
    with PDFReader(TEST_PDF) as reader:
        page = reader.get_page(0)
        norm_q1 = (0.05, 0.08, 0.95, 0.25)
        rect = normalized_to_pdf_rect(page, norm_q1)

        assert rect.x0 >= 0.0
        assert rect.y0 >= 0.0
        assert rect.x1 <= page.rect.width
        assert rect.y1 <= page.rect.height
        assert rect.width > 0
        assert rect.height > 0
