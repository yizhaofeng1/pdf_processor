"""Unit tests for domain models and JSON schema compliance."""

import pytest
import json
from jsonschema import validate
from app.config import SCHEMAS_DIR
from app.models import (
    QuestionSegment,
    Question,
    QuestionType,
    QuestionStatus,
    PageInfo,
    PageType,
    Project,
    DocumentMetadata,
)


def test_question_segment_valid():
    """Verify valid normalized coordinates pass validation."""
    seg = QuestionSegment(page_index=0, normalized_bbox=(0.1, 0.2, 0.9, 0.8))
    assert seg.page_index == 0
    assert seg.normalized_bbox == (0.1, 0.2, 0.9, 0.8)
    assert seg.user_modified is False


def test_question_segment_invalid_bounds():
    """Verify out-of-range coordinates raise ValueError."""
    with pytest.raises(ValueError):
        QuestionSegment(page_index=0, normalized_bbox=(-0.1, 0.2, 0.9, 0.8))

    with pytest.raises(ValueError):
        QuestionSegment(page_index=0, normalized_bbox=(0.1, 0.2, 1.2, 0.8))


def test_question_segment_invalid_order():
    """Verify inverted bounding boxes (x1 >= x2 or y1 >= y2) raise ValueError."""
    with pytest.raises(ValueError):
        QuestionSegment(page_index=0, normalized_bbox=(0.8, 0.2, 0.3, 0.8))

    with pytest.raises(ValueError):
        QuestionSegment(page_index=0, normalized_bbox=(0.1, 0.8, 0.9, 0.2))


def test_question_model_lifecycle():
    """Verify Question creation, segment attachment and status transition."""
    seg = QuestionSegment(page_index=1, normalized_bbox=(0.05, 0.1, 0.95, 0.4))
    q = Question(
        display_number="17",
        question_type=QuestionType.SOLVE,
        segments=[seg],
        confidence=0.98,
    )
    assert q.display_number == "17"
    assert q.question_type == QuestionType.SOLVE
    assert len(q.segments) == 1
    assert q.status == QuestionStatus.DETECTED
    assert q.continuation is False


def test_schema_json_validation():
    """Verify a typical AI JSON response conforms to exam_split_v1.json."""
    schema_path = SCHEMAS_DIR / "exam_split_v1.json"
    assert schema_path.exists()

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    sample_ai_output = {
        "schema_version": "1.0",
        "document": {
            "title": "2024年全国硕士研究生招生考试数学一",
            "subject": "数学一",
            "year": 2024,
            "page_count": 6,
        },
        "pages": [{"page_index": 0, "has_questions": True}],
        "questions": [
            {
                "question_id": "q001",
                "display_number": "1",
                "question_type": "choice",
                "segments": [
                    {
                        "page_index": 0,
                        "normalized_bbox": [0.05, 0.10, 0.95, 0.25],
                    }
                ],
                "confidence": 0.99,
                "review_required": False,
                "reason_codes": [],
            }
        ],
        "warnings": [],
    }

    # Should not raise any ValidationError
    validate(instance=sample_ai_output, schema=schema)
