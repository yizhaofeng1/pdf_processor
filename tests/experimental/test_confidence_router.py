"""Tests for confidence scoring and routing engine."""

from app.experimental.local_ai.config import LocalModelConfig
from app.experimental.local_ai.types import CandidateSegment, LocalQuestionCandidate
from app.experimental.local_detection.confidence_router import LocalConfidenceRouter


def test_confidence_router_high_confidence():
    """Verify clean sequential candidates receive high confidence and skip VLM."""
    cfg = LocalModelConfig(confidence_threshold=0.85, mode="normal")
    router = LocalConfidenceRouter(cfg)

    c1 = LocalQuestionCandidate(
        question_number="1",
        confidence=0.95,
        has_options=True,
        question_type="choice",
        segments=[CandidateSegment(page_index=0, bbox=(0.05, 0.10, 0.45, 0.25))],
    )
    c2 = LocalQuestionCandidate(
        question_number="2",
        confidence=0.95,
        has_options=True,
        question_type="choice",
        segments=[CandidateSegment(page_index=0, bbox=(0.05, 0.30, 0.45, 0.45))],
    )

    routed = router.evaluate_and_route([c1, c2])
    assert routed[0].confidence >= 0.90
    assert routed[0].needs_vlm is False
    assert routed[1].confidence >= 0.90
    assert routed[1].needs_vlm is False


def test_confidence_router_low_confidence_triggers_vlm():
    """Verify sequence gaps or missing options lower confidence and flag needs_vlm."""
    cfg = LocalModelConfig(confidence_threshold=0.85, mode="normal")
    router = LocalConfidenceRouter(cfg)

    # c2 has missing options and sequence gap
    c1 = LocalQuestionCandidate(
        question_number="1",
        confidence=0.95,
        segments=[CandidateSegment(page_index=0, bbox=(0.05, 0.10, 0.45, 0.25))],
    )
    c_gap = LocalQuestionCandidate(
        question_number="5",  # gap from 1 to 5
        confidence=0.80,
        has_options=False,
        question_type="choice",  # expected options but none found
        segments=[CandidateSegment(page_index=0, bbox=(0.05, 0.30, 0.45, 0.31))],  # very tiny height
    )

    routed = router.evaluate_and_route([c1, c_gap])
    assert routed[1].confidence < 0.85
    assert routed[1].needs_vlm is True


def test_confidence_router_fast_mode_bypasses_vlm():
    """Verify fast mode never routes to VLM regardless of confidence."""
    cfg = LocalModelConfig(confidence_threshold=0.85, mode="fast")
    router = LocalConfidenceRouter(cfg)

    c = LocalQuestionCandidate(
        question_number="10",
        confidence=0.50,
        segments=[CandidateSegment(page_index=0, bbox=(0.05, 0.10, 0.45, 0.20))],
    )
    routed = router.evaluate_and_route([c])
    assert routed[0].needs_vlm is False
