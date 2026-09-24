"""Tests for LocalAnalysisService end-to-end orchestration and Question adaptation."""

from pathlib import Path
from app.experimental.local_ai.config import LocalModelConfig
from app.experimental.local_ai.types import (
    CandidateSegment,
    LayoutElement,
    LocalQuestionCandidate,
    OCRBlock,
    QuestionMarker,
)
from app.experimental.local_recognition.service import LocalAnalysisService
from app.models.question import QuestionType


def test_adapt_to_questions():
    """Verify LocalQuestionCandidate instances adapt cleanly to standard Question domain models."""
    service = LocalAnalysisService(config=LocalModelConfig())

    c1 = LocalQuestionCandidate(
        question_number="1",
        confidence=0.98,
        question_type="choice",
        segments=[CandidateSegment(page_index=0, bbox=(0.04, 0.10, 0.48, 0.28))],
    )
    c17 = LocalQuestionCandidate(
        question_number="17",
        confidence=0.92,
        question_type="solution",
        segments=[
            CandidateSegment(page_index=1, bbox=(0.04, 0.50, 0.96, 0.92)),
            CandidateSegment(page_index=2, bbox=(0.04, 0.08, 0.96, 0.30)),
        ],
    )

    questions = service.adapt_to_questions(
        [c1, c17],
        source_pdf_path="/path/to/test.pdf",
        paper_title="test.pdf",
    )

    assert len(questions) == 2

    # Check Q1
    q1 = questions[0]
    assert q1.display_number == "1"
    assert q1.question_type == QuestionType.CHOICE
    assert len(q1.segments) == 1
    assert q1.segments[0].page_index == 0
    assert q1.segments[0].normalized_bbox == (0.04, 0.10, 0.48, 0.28)
    assert q1.continuation is False

    # Check Q17
    q17 = questions[1]
    assert q17.display_number == "17"
    assert q17.question_type == QuestionType.SOLVE
    assert len(q17.segments) == 2
    assert q17.continuation is True
    assert q17.segments[0].page_index == 1
    assert q17.segments[1].page_index == 2


def test_service_with_real_pdf_if_available():
    """Verify service runs on an existing sample PDF if present in workspace."""
    sample_pdf = Path("2020年考研数学一真题.pdf")
    if not sample_pdf.exists():
        return

    cfg = LocalModelConfig(mode="fast")  # Fast rules mode for rapid test
    service = LocalAnalysisService(config=cfg)

    # Process first page only
    questions, analyses = service.process_pdf(
        pdf_path=str(sample_pdf),
        page_indices=[0],
    )

    assert len(analyses) == 1
    assert 0 in analyses
    assert len(questions) > 0

    # Ensure all questions have valid geometry
    for q in questions:
        assert q.display_number.isalnum()
        for seg in q.segments:
            x0, y0, x1, y1 = seg.normalized_bbox
            assert 0.0 <= x0 < x1 <= 1.0
            assert 0.0 <= y0 < y1 <= 1.0
