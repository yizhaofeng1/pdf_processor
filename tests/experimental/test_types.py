"""Tests for local AI data models and schemas."""

import pytest
from app.experimental.local_ai.types import (
    CandidateSegment,
    LayoutElement,
    LocalBoundaryVerification,
    LocalPageAnalysis,
    LocalQuestionCandidate,
    OCRBlock,
    QuestionMarker,
)


def test_layout_element_clamping():
    """Verify LayoutElement clamps coordinates and enforces x1 < x2, y1 < y2."""
    elem = LayoutElement(
        page_index=0,
        category="text",
        bbox=(-0.2, 0.1, 1.5, 0.9),
    )
    assert elem.bbox[0] == 0.0
    assert elem.bbox[1] == 0.1
    assert elem.bbox[2] == 1.0
    assert elem.bbox[3] == 0.9


def test_ocr_block_valid():
    """Verify OCRBlock initialization and validation."""
    blk = OCRBlock(
        text="1. 下列函数中不可导的是",
        bbox=(0.05, 0.10, 0.45, 0.14),
        confidence=0.98,
        page_index=0,
        source="native_pdf",
    )
    assert blk.text.startswith("1.")
    assert blk.source == "native_pdf"


def test_vlm_verification_schema_parse():
    """Verify LocalBoundaryVerification parses strict JSON output correctly."""
    raw_json = """
    {
        "schema_version": "1.0",
        "question_number": "17",
        "accept": true,
        "bbox": [0.04, 0.12, 0.96, 0.88],
        "cross_page": false,
        "contains_all_required_content": true,
        "needs_expand_up": false,
        "needs_expand_down": false,
        "confidence": 0.92,
        "reason_codes": []
    }
    """
    v = LocalBoundaryVerification.model_validate_json(raw_json)
    assert v.accept is True
    assert v.question_number == "17"
    assert v.bbox == (0.04, 0.12, 0.96, 0.88)
    assert v.confidence == 0.92


def test_vlm_verification_clamping():
    """Verify invalid negative or oversized bboxes in VLM output are clamped safely."""
    raw_json = """
    {
        "schema_version": "1.0",
        "question_number": "1",
        "accept": false,
        "bbox": [-0.1, 0.05, 1.2, 0.3],
        "cross_page": false,
        "contains_all_required_content": false,
        "needs_expand_up": true,
        "needs_expand_down": false,
        "confidence": 0.65,
        "reason_codes": ["MISSING_STEM"]
    }
    """
    v = LocalBoundaryVerification.model_validate_json(raw_json)
    assert v.bbox[0] == 0.0
    assert v.bbox[2] == 1.0
    assert "MISSING_STEM" in v.reason_codes
