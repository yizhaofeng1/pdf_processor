"""Unit tests for CandidateBuilder: Region merging, neighbor expansion, and overlap detection."""

from app.experimental.local_recognition.candidate_builder import CandidateBuilder
from app.experimental.local_recognition.page_table import VirtualPageTable
from app.experimental.local_recognition.types import CoarseQuestionOutput


def test_candidate_builder_merging_and_padding():
    table = VirtualPageTable(page_index=0, page_rect=(0.0, 0.0, 600.0, 800.0), rows=8, columns=4)

    # Question covering R1C0, R1C1, R2C0, R2C1
    q1 = CoarseQuestionOutput(
        question_number="1",
        regions=["P00:R01:C00", "P00:R01:C01", "P00:R02:C00", "P00:R02:C01"],
        confidence=0.95,
    )

    builder = CandidateBuilder(neighbor_radius=0, padding_ratio=(0.01, 0.01))
    candidates = builder.build_candidates_for_page(table, [q1])

    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.question_number == "1"
    assert cand.page_index == 0

    # R1C0 ~ R2C1 normalized range: x in [0.0, 0.5], y in [0.125, 0.375]
    # With padding (0.01, 0.01): x in [0.0, 0.51], y in [0.115, 0.385]
    x1, y1, x2, y2 = cand.normalized_rect
    assert x1 == 0.0  # Clamped at 0.0
    assert abs(y1 - (0.125 - 0.01)) < 1e-4
    assert abs(x2 - (0.500 + 0.01)) < 1e-4
    assert abs(y2 - (0.375 + 0.01)) < 1e-4


def test_candidate_builder_neighbor_expansion():
    table = VirtualPageTable(page_index=0, page_rect=(0.0, 0.0, 600.0, 800.0), rows=8, columns=4)

    # Question covering just R4C2
    q1 = CoarseQuestionOutput(
        question_number="5",
        regions=["P00:R04:C02"],
    )

    builder_expanded = CandidateBuilder(neighbor_radius=1)
    candidates_expanded = builder_expanded.build_candidates_for_page(table, [q1])

    assert len(candidates_expanded) == 1
    cand_exp = candidates_expanded[0]
    assert cand_exp.expanded is True

    # With neighbor_radius=1, R4C2 expands to R3~R5 and C1~C3
    # R3~R5 rows: y in [3/8, 6/8] = [0.375, 0.750]
    # C1~C3 cols: x in [1/4, 4/4] = [0.250, 1.000]
    x1, y1, x2, y2 = cand_exp.normalized_rect
    assert x1 <= 0.25
    assert y1 <= 0.375
    assert x2 >= 1.0 - 1e-4
    assert y2 >= 0.75 - 1e-4


def test_candidate_builder_overlap_detection():
    table = VirtualPageTable(page_index=0, page_rect=(0.0, 0.0, 600.0, 800.0), rows=8, columns=4)

    # Q1 and Q2 share almost the same regions
    q1 = CoarseQuestionOutput(question_number="17", regions=["P00:R04:C00", "P00:R04:C01"])
    q2 = CoarseQuestionOutput(question_number="18", regions=["P00:R04:C00", "P00:R04:C01", "P00:R05:C00"])

    builder = CandidateBuilder(neighbor_radius=0, overlap_threshold=0.3)
    candidates = builder.build_candidates_for_page(table, [q1, q2])

    assert len(candidates) == 2
    assert candidates[0].overlap_detected is True
    assert candidates[1].overlap_detected is True
    assert candidates[0].verify_required is True
    assert candidates[1].verify_required is True


def test_candidate_builder_full_width_layout():
    table = VirtualPageTable(page_index=0, page_rect=(0.0, 0.0, 600.0, 800.0), rows=8, columns=4)
    # Question covering only C00
    q1 = CoarseQuestionOutput(question_number="1", regions=["P00:R01:C00"])

    builder = CandidateBuilder(full_width_layout=True)
    candidates = builder.build_candidates_for_page(table, [q1])

    assert len(candidates) == 1
    cand = candidates[0]
    # In full_width_layout mode, normalized x should span full width [0.0, 1.0]
    assert cand.normalized_rect[0] == 0.0
    assert cand.normalized_rect[2] == 1.0


def test_candidate_builder_sequential_interpolation():
    table = VirtualPageTable(page_index=0, page_rect=(0.0, 0.0, 600.0, 800.0), rows=8, columns=4)
    # Detected Q1 and Q3, missing Q2
    q1 = CoarseQuestionOutput(question_number="1", regions=["P00:R00:C00", "P00:R01:C00"])
    q3 = CoarseQuestionOutput(question_number="3", regions=["P00:R03:C00", "P00:R04:C00"])

    builder = CandidateBuilder(full_width_layout=True)
    candidates = builder.build_candidates_for_page(table, [q1, q3])

    # Should interpolate Q2 between Q1 and Q3
    q_nums = [c.question_number for c in candidates]
    assert "2" in q_nums
    assert q_nums == ["1", "2", "3"]
