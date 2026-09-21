"""Unit tests for Pydantic Schema parsing and Prompt Builder."""

import pytest
from pydantic import ValidationError

from app.experimental.local_recognition.types import (
    CoarsePageOutput,
    CoarseQuestionOutput,
    LocalRefineOutput,
)
from app.experimental.local_recognition.prompt_builder import ExperimentPromptBuilder


def test_coarse_page_output_parsing():
    raw = {
        "schema_version": "vaql-coarse-v1",
        "page_index": 3,
        "questions": [
            {
                "question_number": "17",
                "regions": ["P03:R04:C00", "P03:R04:C01"],
                "confidence": 0.95,
                "cross_page": False,
            }
        ],
    }
    parsed = CoarsePageOutput.model_validate(raw)
    assert parsed.page_index == 3
    assert len(parsed.questions) == 1
    assert parsed.questions[0].question_number == "17"
    assert parsed.questions[0].regions == ["P03:R04:C00", "P03:R04:C01"]


def test_coarse_page_output_invalid():
    # Negative page_index
    with pytest.raises(ValidationError):
        CoarsePageOutput.model_validate({"page_index": -1, "questions": []})


def test_local_refine_output_parsing_and_self_healing():
    raw = {
        "schema_version": "vaql-local-v1",
        "question_number": "17",
        "bbox": [0.05, 0.1, 0.95, 0.9],
        "confidence": 0.92,
        "boundary_complete": True,
        "needs_neighbor": False,
    }
    parsed = LocalRefineOutput.model_validate(raw)
    assert parsed.question_number == "17"
    assert parsed.bbox == (0.05, 0.1, 0.95, 0.9)

    # Inverted bbox should self-heal (x1 > x2 or y1 > y2)
    raw_inverted = {
        "question_number": "17",
        "bbox": [0.95, 0.9, 0.05, 0.1],
    }
    healed = LocalRefineOutput.model_validate(raw_inverted)
    assert healed.bbox == (0.05, 0.1, 0.95, 0.9)

    # Clamping values outside [0.0, 1.0]
    raw_out_of_bounds = {
        "question_number": "17",
        "bbox": [-0.1, -0.2, 1.2, 1.5],
    }
    clamped = LocalRefineOutput.model_validate(raw_out_of_bounds)
    assert clamped.bbox == (0.0, 0.0, 1.0, 1.0)


def test_prompt_builder():
    builder = ExperimentPromptBuilder()

    coarse_p = builder.build_coarse_prompt(page_index=2, grid_rows=8, grid_columns=4)
    assert "P02" in coarse_p
    assert "8 行 × 4 列" in coarse_p

    refine_p = builder.build_local_refine_prompt(question_number="18")
    assert "第 18 题" in refine_p

    verify_p = builder.build_verify_prompt(q1_number="17", q2_number="18")
    assert "第 17 题 与 第 18 题" in verify_p
