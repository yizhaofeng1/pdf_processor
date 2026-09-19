"""Unit tests for Adaptive Blank Export and Multi-Source PDF Export."""

from pathlib import Path
import pytest
import pymupdf

from app.models.question import Question, QuestionType
from app.models.segment import QuestionSegment
from app.pdf.exporter import PDFExporter, ExportOptions, ExportMode


@pytest.fixture
def pdf_paths():
    p1 = Path(__file__).resolve().parent.parent.parent / "2010_math_test.pdf"
    p2 = Path(__file__).resolve().parent.parent.parent / "2019年考研数学一真题.pdf"
    assert p1.exists(), f"Missing test PDF: {p1}"
    assert p2.exists(), f"Missing test PDF: {p2}"
    return p1, p2


def test_adaptive_exam_flow_export(pdf_paths, tmp_path):
    p1, p2 = pdf_paths

    # Create questions from two different PDF files
    q1 = Question(
        display_number="1",
        question_type="选择题",
        source_pdf_path=str(p1),
        source_paper_title="2010年真题",
        segments=[
            QuestionSegment(
                page_index=0,
                normalized_bbox=(0.08, 0.12, 0.92, 0.22),
            )
        ],
    )

    q2 = Question(
        display_number="2",
        question_type="填空题",
        source_pdf_path=str(p1),
        source_paper_title="2010年真题",
        segments=[
            QuestionSegment(
                page_index=1,
                normalized_bbox=(0.08, 0.15, 0.92, 0.26),
            )
        ],
    )

    q3 = Question(
        display_number="3",
        question_type="解答题",
        source_pdf_path=str(p2),
        source_paper_title="2019年真题",
        segments=[
            QuestionSegment(
                page_index=2,
                normalized_bbox=(0.08, 0.20, 0.92, 0.45),
            )
        ],
    )

    out_path = tmp_path / "adaptive_multi_source_test.pdf"

    options = ExportOptions(
        mode=ExportMode.ADAPTIVE_EXAM_FLOW,
        large_blank_height_pt=180.0,
        show_answer_box=True,
        renumber_sequentially=True,
        show_source_footnote=True,
        paper_title="高数模拟精选组卷 (自适应空白)",
    )

    result_path = PDFExporter.export(p1, [q1, q2, q3], out_path, options)

    assert result_path.exists()
    assert result_path.stat().st_size > 0

    # Validate generated PDF with PyMuPDF
    doc = pymupdf.open(str(result_path))
    assert doc.page_count >= 1

    # Check page text for exam title and answer box
    found_title = False
    found_answer_box = False
    for page in doc:
        text = page.get_text()
        if "高数模拟精选组卷" in text:
            found_title = True
        if "【答题草稿区域】" in text:
            found_answer_box = True

    assert found_title is True
    assert found_answer_box is True
    doc.close()


def test_compact_multi_source_export(pdf_paths, tmp_path):
    p1, p2 = pdf_paths

    q1 = Question(
        display_number="1",
        question_type="小题",
        source_pdf_path=str(p1),
        source_paper_title="2010年真题",
        segments=[QuestionSegment(page_index=0, normalized_bbox=(0.08, 0.12, 0.92, 0.25))],
    )
    q2 = Question(
        display_number="2",
        question_type="大题",
        source_pdf_path=str(p2),
        source_paper_title="2019年真题",
        segments=[QuestionSegment(page_index=0, normalized_bbox=(0.08, 0.12, 0.92, 0.35))],
    )

    out_path = tmp_path / "compact_multi_source_test.pdf"
    options = ExportOptions(
        mode=ExportMode.COMPACT_FLOW,
        renumber_sequentially=False,
        show_source_footnote=True,
    )

    result_path = PDFExporter.export(p1, [q1, q2], out_path, options)
    assert result_path.exists()

    doc = pymupdf.open(str(result_path))
    assert doc.page_count >= 1
    doc.close()
