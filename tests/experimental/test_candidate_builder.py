"""Tests for candidate builder and option aggregation."""

from app.experimental.local_ai.types import LayoutElement, OCRBlock, QuestionMarker
from app.experimental.local_detection.candidate_builder import LocalCandidateBuilder


def test_candidate_builder_multiple_choice():
    """Verify multiple-choice candidates group all options A-D and identify choice question type."""
    builder = LocalCandidateBuilder()

    markers = [
        QuestionMarker(number="1", page_index=0, bbox=(0.05, 0.10, 0.15, 0.12), confidence=0.95),
        QuestionMarker(number="2", page_index=0, bbox=(0.05, 0.35, 0.15, 0.37), confidence=0.95),
    ]

    elements = [
        LayoutElement(page_index=0, category="text", bbox=(0.05, 0.10, 0.45, 0.14)),
        LayoutElement(page_index=0, category="formula", bbox=(0.10, 0.15, 0.40, 0.18)),
        LayoutElement(page_index=0, category="text", bbox=(0.05, 0.20, 0.45, 0.30)),
    ]

    blocks = [
        OCRBlock(text="1. 当 x->0 时，与 x 等价的无穷小量是", bbox=(0.05, 0.10, 0.45, 0.13), page_index=0),
        OCRBlock(text="(A) e^x - 1", bbox=(0.05, 0.20, 0.22, 0.23), page_index=0),
        OCRBlock(text="(B) sin x", bbox=(0.25, 0.20, 0.42, 0.23), page_index=0),
        OCRBlock(text="(C) tan x", bbox=(0.05, 0.25, 0.22, 0.28), page_index=0),
        OCRBlock(text="(D) ln(1+x)", bbox=(0.25, 0.25, 0.42, 0.28), page_index=0),
        OCRBlock(text="2. 设函数 f(x) 可导", bbox=(0.05, 0.35, 0.45, 0.38), page_index=0),
    ]

    candidates = builder.build_candidates_for_page(
        page_index=0,
        markers=markers,
        layout_elements=elements,
        text_blocks=blocks,
        is_two_column=False,
    )

    assert len(candidates) == 2
    q1 = candidates[0]
    assert q1.question_number == "1"
    assert q1.has_options is True
    assert set(q1.options_found) == {"A", "B", "C", "D"}
    assert q1.question_type == "choice"
    assert len(q1.segments) == 1
    assert q1.segments[0].bbox[1] <= 0.10
    assert q1.segments[0].bbox[3] >= 0.28
