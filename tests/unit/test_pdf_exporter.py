"""Unit tests for lossless PDF cropper and exporter engine."""

import pytest
from pathlib import Path
import pymupdf

from app.pdf.cropper import calculate_fit_rect, A4_WIDTH, A4_HEIGHT
from app.pdf.exporter import PDFExporter, ExportMode, ExportOptions
from app.models.question import Question, QuestionType
from app.models.segment import QuestionSegment


@pytest.fixture
def sample_pdf():
    return Path("2010_math_test.pdf").resolve()


def test_calculate_fit_rect():
    """Verify aspect ratio preserving target rect calculation."""
    # Source: 400 x 200 (2:1 aspect ratio)
    # Target: 500 x 500
    s_rect = (0, 0, 400, 200)
    t_bounds = (50, 50, 550, 550)

    dest = calculate_fit_rect(s_rect, t_bounds, max_scale=1.0, align="center")
    assert dest.width == 400
    assert dest.height == 200
    assert dest.y0 == 50
    # Horizontally centered inside 500 pt width (start at 50 + (500-400)/2 = 100)
    assert abs(dest.x0 - 100) < 1.0


def test_export_single_per_page(sample_pdf, tmp_path):
    """Verify A4 Single-Question-Per-Page export creates valid A4 pages."""
    out_pdf = tmp_path / "export_single.pdf"

    q1 = Question(
        display_number="1",
        question_type=QuestionType.CHOICE,
        segments=[
            QuestionSegment(page_index=0, normalized_bbox=(0.05, 0.08, 0.95, 0.30))
        ],
        selected=True,
    )
    q2 = Question(
        display_number="2",
        question_type=QuestionType.FILL_IN,
        segments=[
            QuestionSegment(page_index=0, normalized_bbox=(0.05, 0.32, 0.95, 0.55))
        ],
        selected=True,
    )

    opts = ExportOptions(
        mode=ExportMode.SINGLE_QUESTION_PER_PAGE,
        paper_title="2010真题考研数学精选",
        show_header=True,
        show_footer=True,
    )

    res_path = PDFExporter.export(
        source_pdf=sample_pdf,
        questions=[q1, q2],
        output_path=out_pdf,
        options=opts,
    )

    assert res_path.exists()
    assert res_path.stat().st_size > 1000

    doc = pymupdf.open(str(res_path))
    assert len(doc) == 2

    # Check A4 dimensions
    p0 = doc[0]
    assert abs(p0.rect.width - A4_WIDTH) < 1.0
    assert abs(p0.rect.height - A4_HEIGHT) < 1.0

    doc.close()


def test_export_compact_flow(sample_pdf, tmp_path):
    """Verify A4 Compact Flow mode batches small segments onto single A4 sheet."""
    out_pdf = tmp_path / "export_compact.pdf"

    q1 = Question(
        display_number="1",
        segments=[QuestionSegment(page_index=0, normalized_bbox=(0.05, 0.10, 0.95, 0.25))],
        selected=True,
    )
    q2 = Question(
        display_number="2",
        segments=[QuestionSegment(page_index=0, normalized_bbox=(0.05, 0.26, 0.95, 0.40))],
        selected=True,
    )

    opts = ExportOptions(mode=ExportMode.COMPACT_FLOW, show_header=True, show_footer=True)

    res_path = PDFExporter.export(
        source_pdf=sample_pdf,
        questions=[q1, q2],
        output_path=out_pdf,
        options=opts,
    )

    assert res_path.exists()
    doc = pymupdf.open(str(res_path))
    # Since two small questions fit on one page, compact mode should produce 1 A4 page!
    assert len(doc) == 1
    doc.close()


def test_export_empty_selection_raises(sample_pdf, tmp_path):
    """Verify ValueError is raised when no questions are selected for export."""
    out_pdf = tmp_path / "empty.pdf"
    q_unselected = Question(display_number="1", selected=False)

    with pytest.raises(ValueError, match="未选择任何题目"):
        PDFExporter.export(
            source_pdf=sample_pdf,
            questions=[q_unselected],
            output_path=out_pdf,
        )
