"""Tests for cross-page question continuity resolver."""

from app.experimental.local_ai.types import (
    CandidateSegment,
    LocalPageAnalysis,
    LocalQuestionCandidate,
    OCRBlock,
    QuestionMarker,
)
from app.experimental.local_detection.cross_page import LocalCrossPageResolver


def test_cross_page_continuity():
    """Verify question ending at bottom of Page 1 continues onto top of Page 2."""
    resolver = LocalCrossPageResolver()

    # Page 0: Q17 ends at y=0.92
    q17 = LocalQuestionCandidate(
        question_number="17",
        segments=[CandidateSegment(page_index=0, bbox=(0.05, 0.65, 0.95, 0.92))],
    )

    # Page 1: Starts with subquestion (2) formula before Q18
    p1_blocks = [
        OCRBlock(text="(2) 求证当 x>0 时，不等式成立。", bbox=(0.05, 0.10, 0.85, 0.14), page_index=1),
        OCRBlock(text="18. 设常微分方程", bbox=(0.05, 0.35, 0.85, 0.38), page_index=1),
    ]
    p1_analysis = LocalPageAnalysis(
        page_index=1,
        text_blocks=p1_blocks,
        markers=[QuestionMarker(number="18", page_index=1, bbox=(0.05, 0.35, 0.15, 0.37))],
    )

    q18 = LocalQuestionCandidate(
        question_number="18",
        segments=[CandidateSegment(page_index=1, bbox=(0.05, 0.35, 0.95, 0.60))],
    )

    merged = resolver.resolve_cross_page_candidates(
        candidates_by_page={0: [q17], 1: [q18]},
        page_analyses={0: LocalPageAnalysis(page_index=0), 1: p1_analysis},
    )

    # Q17 should now have 2 segments
    assert len(merged) == 2
    assert merged[0].question_number == "17"
    assert len(merged[0].segments) == 2
    assert merged[0].segments[0].page_index == 0
    assert merged[0].segments[1].page_index == 1
    assert merged[0].segments[1].bbox[1] <= 0.10
    assert merged[0].segments[1].bbox[3] < 0.35
