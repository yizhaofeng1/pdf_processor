"""Tests for boundary resolution, padding application, and overlap resolution."""

from app.experimental.local_ai.config import LocalModelConfig
from app.experimental.local_ai.types import CandidateSegment, LocalQuestionCandidate
from app.experimental.local_detection.boundary_resolver import LocalBoundaryResolver


def test_boundary_resolver_padding_and_large_question():
    """Verify safety padding and full-width expansion for large questions."""
    cfg = LocalModelConfig(pad_ratio_x=0.015, pad_ratio_y=0.010)
    resolver = LocalBoundaryResolver(cfg)

    # Large question (Q17)
    seg17 = CandidateSegment(
        page_index=0,
        bbox=(0.06, 0.40, 0.70, 0.60),
    )
    c17 = LocalQuestionCandidate(
        question_number="17",
        segments=[seg17],
        question_type="solution",
    )

    resolved = resolver.resolve_candidates([c17], is_two_column=False)
    r_seg = resolved[0].segments[0]

    # Large question must expand to full width
    assert r_seg.bbox[0] <= 0.045
    assert r_seg.bbox[2] >= 0.955
    # y must be padded
    assert r_seg.bbox[1] <= 0.390
    assert r_seg.bbox[3] >= 0.610


def test_boundary_resolver_consecutive_collision():
    """Verify vertical overlap between consecutive questions is safely resolved."""
    cfg = LocalModelConfig()
    resolver = LocalBoundaryResolver(cfg)

    c1 = LocalQuestionCandidate(
        question_number="1",
        segments=[CandidateSegment(page_index=0, bbox=(0.05, 0.10, 0.45, 0.32))],
    )
    c2 = LocalQuestionCandidate(
        question_number="2",
        segments=[CandidateSegment(page_index=0, bbox=(0.05, 0.30, 0.45, 0.50))],
    )

    resolved = resolver.resolve_candidates([c1, c2], is_two_column=False)
    # c1 bottom must not collide into c2 top
    assert resolved[0].segments[0].bbox[3] <= resolved[1].segments[0].bbox[1]
