"""Unit tests for Question model types, helpers, and serialization."""

import pytest
from app.models.question import Question, QuestionType, QuestionStatus
from app.models.segment import QuestionSegment


def test_question_type_helpers():
    # Small questions
    q_choice = Question(display_number="1", question_type=QuestionType.CHOICE)
    assert q_choice.is_small_question() is True
    assert q_choice.is_large_question() is False
    assert q_choice.get_type_display_name() == "选择题"

    q_fill = Question(display_number="9", question_type="填空题")
    assert q_fill.is_small_question() is True
    assert q_fill.is_large_question() is False
    assert q_fill.get_type_display_name() == "填空题"

    q_small = Question(display_number="2", question_type="小题")
    assert q_small.is_small_question() is True
    assert q_small.is_large_question() is False
    assert q_small.get_type_display_name() == "小题"

    # Large questions
    q_solve = Question(display_number="15", question_type=QuestionType.SOLVE)
    assert q_solve.is_small_question() is False
    assert q_solve.is_large_question() is True
    assert q_solve.get_type_display_name() == "解答题"

    q_proof = Question(display_number="19", question_type="证明题")
    assert q_proof.is_small_question() is False
    assert q_proof.is_large_question() is True
    assert q_proof.get_type_display_name() == "证明题"

    q_large = Question(display_number="20", question_type="大题")
    assert q_large.is_small_question() is False
    assert q_large.is_large_question() is True
    assert q_large.get_type_display_name() == "大题"


def test_question_source_metadata_serialization():
    q = Question(
        display_number="3",
        original_display_number="15",
        question_type="大题",
        source_pdf_path="/path/to/paper_2020.pdf",
        source_paper_title="paper_2020",
        segments=[
            QuestionSegment(
                page_index=2,
                normalized_bbox=(0.1, 0.2, 0.9, 0.5),
            )
        ],
    )

    data = q.model_dump()
    assert data["source_pdf_path"] == "/path/to/paper_2020.pdf"
    assert data["source_paper_title"] == "paper_2020"
    assert data["original_display_number"] == "15"

    q_restored = Question.model_validate(data)
    assert q_restored.source_pdf_path == "/path/to/paper_2020.pdf"
    assert q_restored.source_paper_title == "paper_2020"
    assert q_restored.original_display_number == "15"
    assert q_restored.is_large_question() is True
