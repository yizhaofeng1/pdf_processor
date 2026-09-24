"""Unit tests for Phase 4 detection pipeline."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from app.models.question import Question, QuestionType, QuestionStatus, AnchorPoint
from app.models.segment import QuestionSegment
from app.models.ai_result import VisionAnalysisResult
from app.detection.marker_detector import QuestionMarker, AIMarkerDetector
from app.detection.boundary_resolver import BoundaryResolver
from app.detection.cross_page_resolver import CrossPageResolver
from app.detection.consistency import ConsistencyChecker
from app.storage.database import init_db, save_project_questions, load_project_questions
from app.services.detection_service import DetectionService


def test_boundary_resolver_single_column():
    """Test boundary derivation for single-column page markers."""
    resolver = BoundaryResolver()
    markers = [
        QuestionMarker(number="1", page_index=0, normalized_point=(0.05, 0.10)),
        QuestionMarker(number="2", page_index=0, normalized_point=(0.05, 0.35)),
        QuestionMarker(number="3", page_index=0, normalized_point=(0.05, 0.65)),
    ]

    questions = resolver.resolve_page_questions(markers, page_index=0)
    assert len(questions) == 3
    assert questions[0].display_number == "1"
    assert questions[1].display_number == "2"
    assert questions[2].display_number == "3"

    # Verify vertical bounding boxes
    seg0 = questions[0].segments[0]
    seg1 = questions[1].segments[0]
    seg2 = questions[2].segments[0]

    assert seg0.normalized_bbox[1] < seg0.normalized_bbox[3]
    # Q1 bottom should be near Q2 top
    assert abs(seg0.normalized_bbox[3] - 0.35) < 0.05
    # Q3 extends towards page bottom limit
    assert seg2.normalized_bbox[3] >= 0.90


def test_boundary_resolver_two_column():
    """Test boundary derivation when markers are split across two columns."""
    resolver = BoundaryResolver()
    markers = [
        QuestionMarker(number="1", page_index=0, normalized_point=(0.05, 0.10)),
        QuestionMarker(number="2", page_index=0, normalized_point=(0.05, 0.50)),
        QuestionMarker(number="3", page_index=0, normalized_point=(0.55, 0.10)),
        QuestionMarker(number="4", page_index=0, normalized_point=(0.55, 0.50)),
    ]

    questions = resolver.resolve_page_questions(markers, page_index=0)
    assert len(questions) == 4
    # Column 1 questions should be in left column (x < 0.5)
    assert questions[0].segments[0].normalized_bbox[2] <= 0.50
    assert questions[1].segments[0].normalized_bbox[2] <= 0.50
    # Column 2 questions should be in right column (x > 0.5)
    assert questions[2].segments[0].normalized_bbox[0] >= 0.50
    assert questions[3].segments[0].normalized_bbox[0] >= 0.50


def test_boundary_resolver_text_snapping():
    """Test boundary resolver snaps to native PDF vector text blocks for solve questions."""
    resolver = BoundaryResolver()
    markers = [
        QuestionMarker(
            number="17",
            page_index=0,
            normalized_point=(0.05, 0.15),
            normalized_bbox=(0.05, 0.15, 0.95, 0.50),  # Exaggerated blank space
            question_type=QuestionType.SOLVE,
        ),
    ]
    # Simulate page size 500x1000
    # Text block extends slightly higher (y=140 -> norm 0.14) and ends at y=290 (norm 0.29)
    mock_blocks = [
        (25, 140, 480, 290, "Sample solve question text and sub-questions (I)(II)", 0, 0),
    ]

    questions = resolver.resolve_page_questions(
        markers,
        page_index=0,
        page_width=500.0,
        page_height=1000.0,
        text_blocks=mock_blocks,
    )
    assert len(questions) == 1
    bbox = questions[0].segments[0].normalized_bbox
    # y1 preserves AI start position and does not pull upwards into section headers
    assert bbox[1] <= 0.15
    # Should contract y2 from 0.50 down towards 0.29 + 0.012 (~0.302) to lop off blank space
    assert bbox[3] <= 0.31


def test_boundary_resolver_dense_small_visual_trust():
    """Test boundary resolver trusts AI visual bounding box for dense small questions."""
    resolver = BoundaryResolver()
    markers = [
        QuestionMarker(
            number="1",
            page_index=0,
            normalized_point=(0.05, 0.15),
            normalized_bbox=(0.05, 0.15, 0.95, 0.28),
            question_type=QuestionType.CHOICE,
        ),
    ]
    mock_blocks = [
        (25, 130, 480, 320, "Surrounding text that shouldn't distort choice box", 0, 0),
    ]

    questions = resolver.resolve_page_questions(
        markers,
        page_index=0,
        page_width=500.0,
        page_height=1000.0,
        text_blocks=mock_blocks,
    )
    assert len(questions) == 1
    bbox = questions[0].segments[0].normalized_bbox
    # Trusts AI visual bounding box directly (y1=0.15, y2=0.28)
    assert bbox[1] == 0.15
    assert bbox[3] == 0.28


def test_cross_page_resolver_merging():
    """Test merging multi-page question into single Question with 2 segments."""
    resolver = CrossPageResolver(bottom_threshold=0.80)

    # Page 0: Q16 ends near bottom (0.88)
    q16 = Question(
        display_number="16",
        segments=[
            QuestionSegment(page_index=0, normalized_bbox=(0.04, 0.60, 0.96, 0.90))
        ],
    )
    # Page 1: Q17 starts mid-page at y=0.40, preceded by continuation of Q16
    q17 = Question(
        display_number="17",
        segments=[
            QuestionSegment(page_index=1, normalized_bbox=(0.04, 0.40, 0.96, 0.85))
        ],
    )

    page_map = {0: [q16], 1: [q17]}
    merged = resolver.resolve(page_map, page_count=2)

    assert len(merged) == 2
    merged_q16 = [q for q in merged if q.display_number == "16"][0]
    assert merged_q16.continuation is True
    assert len(merged_q16.segments) == 2
    assert merged_q16.segments[0].page_index == 0
    assert merged_q16.segments[1].page_index == 1
    # Continuation segment should occupy top of page 1 up to Q17 start
    assert merged_q16.segments[1].normalized_bbox[1] <= 0.05
    assert merged_q16.segments[1].normalized_bbox[3] <= 0.40


def test_consistency_checker_missing_numbers_and_overlaps():
    """Test consistency checker detecting missing question number and segment overlaps."""
    checker = ConsistencyChecker()

    # Create questions with missing number: 1, 2, 4 (missing 3)
    q1 = Question(
        display_number="1",
        segments=[QuestionSegment(page_index=0, normalized_bbox=(0.05, 0.05, 0.95, 0.20))],
    )
    q2 = Question(
        display_number="2",
        # Overlapping with Q4
        segments=[QuestionSegment(page_index=0, normalized_bbox=(0.05, 0.20, 0.95, 0.60))],
    )
    q4 = Question(
        display_number="4",
        # Overlaps significantly with Q2 (from y=0.30 to 0.60)
        segments=[QuestionSegment(page_index=0, normalized_bbox=(0.05, 0.30, 0.95, 0.70))],
    )

    questions = [q1, q2, q4]
    checked = checker.check(questions)

    assert any(q.review_required for q in checked)
    # Check for missing number warning
    assert any("MISSING_QUESTION_NUMBER" in q.reason_codes for q in checked)
    # Check for overlap warning
    assert any("OVERLAP_DETECTED" in q.reason_codes for q in checked)


def test_database_persistence_roundtrip(tmp_path):
    """Test saving and loading questions to SQLite database."""
    db_file = tmp_path / "test_exam.db"
    init_db(db_file)

    q1 = Question(
        display_number="1",
        question_type=QuestionType.CHOICE,
        segments=[
            QuestionSegment(page_index=0, normalized_bbox=(0.04, 0.10, 0.96, 0.30))
        ],
        confidence=0.98,
        selected=True,
    )
    q2 = Question(
        display_number="2",
        question_type=QuestionType.FILL_IN,
        segments=[
            QuestionSegment(page_index=0, normalized_bbox=(0.04, 0.31, 0.96, 0.55)),
            QuestionSegment(page_index=1, normalized_bbox=(0.04, 0.05, 0.96, 0.20)),
        ],
        confidence=0.85,
        review_required=True,
        selected=False,
    )

    save_project_questions("proj_test", [q1, q2], db_path=db_file)
    loaded = load_project_questions("proj_test", db_path=db_file)

    assert len(loaded) == 2
    assert loaded[0].display_number == "1"
    assert loaded[0].question_type == "choice"
    assert len(loaded[0].segments) == 1

    assert loaded[1].display_number == "2"
    assert loaded[1].review_required is True
    assert loaded[1].selected is False
    assert len(loaded[1].segments) == 2
    assert loaded[1].continuation is True


def test_detection_service_with_mock_provider(tmp_path, monkeypatch):
    """Test DetectionService execution with a mock vision provider."""
    from app.pdf.renderer import PDFRenderer
    monkeypatch.setattr(
        PDFRenderer,
        "render_page_to_image_file",
        lambda reader, page_idx, out_path, dpi=180: Path(out_path).touch(),
    )

    # Mock PDFReader
    mock_reader = MagicMock()
    mock_reader.file_hash = "abcdef123456"
    mock_reader.page_count = 2
    mock_page_info = MagicMock()
    mock_page_info.width = 595.0
    mock_page_info.height = 842.0
    from app.pdf.reader import PageType
    mock_page_info.page_type = PageType.IMAGE_PDF
    mock_reader.get_page_info.return_value = mock_page_info
    mock_reader.file_path = str(tmp_path / "mock.pdf")

    # Mock Provider returning VisionAnalysisResult
    mock_provider = MagicMock()
    mock_provider.analyze_pages.side_effect = [
        VisionAnalysisResult(
            questions=[
                Question(
                    display_number="1",
                    segments=[QuestionSegment(page_index=0, normalized_bbox=(0.05, 0.08, 0.95, 0.30))],
                ),
                Question(
                    display_number="2",
                    segments=[QuestionSegment(page_index=0, normalized_bbox=(0.05, 0.32, 0.95, 0.60))],
                ),
            ]
        ),
        VisionAnalysisResult(
            questions=[
                Question(
                    display_number="3",
                    segments=[QuestionSegment(page_index=1, normalized_bbox=(0.05, 0.08, 0.95, 0.45))],
                )
            ]
        ),
    ]

    service = DetectionService(provider=mock_provider)
    progress_calls = []

    questions = service.run_pipeline(
        mock_reader,
        project_id="test_run",
        progress_callback=lambda cur, tot, msg: progress_calls.append((cur, tot, msg)),
    )

    assert len(questions) == 3
    assert questions[0].display_number == "1"
    assert questions[1].display_number == "2"
    assert questions[2].display_number == "3"
    assert len(progress_calls) > 0
    # Segments must have computed pdf_bbox
    for q in questions:
        for seg in q.segments:
            assert seg.pdf_bbox is not None


def test_boundary_resolver_anti_engulfment():
    """Verify that an oversized or hallucinated AI bounding box does not engulf following questions."""
    resolver = BoundaryResolver()
    markers = [
        QuestionMarker(
            number="(17)",
            page_index=2,
            normalized_point=(0.033, 0.013),
            normalized_bbox=(0.033, 0.013, 0.598, 0.60),  # Oversized model output!
        ),
        QuestionMarker(
            number="(18)",
            page_index=2,
            normalized_point=(0.033, 0.179),
            normalized_bbox=(0.033, 0.179, 0.735, 0.329),
        ),
        QuestionMarker(
            number="(19)",
            page_index=2,
            normalized_point=(0.033, 0.472),
            normalized_bbox=(0.033, 0.472, 0.967, 0.54),
        ),
        QuestionMarker(
            number="(20)",
            page_index=2,
            normalized_point=(0.033, 0.684),
            normalized_bbox=(0.033, 0.684, 0.967, 0.803),
        ),
    ]

    questions = resolver.resolve_page_questions(markers, page_index=2)
    assert len(questions) == 4
    # All display numbers sanitized to pure digits
    assert questions[0].display_number == "17"
    assert questions[1].display_number == "18"
    assert questions[2].display_number == "19"
    assert questions[3].display_number == "20"

    q17_box = questions[0].segments[0].normalized_bbox
    q18_box = questions[1].segments[0].normalized_bbox
    q19_box = questions[2].segments[0].normalized_bbox
    q20_box = questions[3].segments[0].normalized_bbox

    # Q17 must strictly end BEFORE Q18 starts
    assert q17_box[3] <= q18_box[1] + 0.005
    assert q17_box[3] < 0.18

    # Q18 must strictly end BEFORE Q19 starts
    assert q18_box[3] <= q19_box[1] + 0.005
    assert q18_box[3] < 0.48

    # Q19 must strictly end BEFORE Q20 starts
    assert q19_box[3] <= q20_box[1] + 0.005
    assert q19_box[3] < 0.69

    # None of the questions should be compressed into tiny slivers
    for q in questions:
        seg = q.segments[0]
        h = seg.normalized_bbox[3] - seg.normalized_bbox[1]
        assert h >= 0.05, f"Question {q.display_number} height {h} is too small"


def test_boundary_resolver_resists_stray_right_marker():
    """Ensure a stray noisy marker on the right does not trick the resolver into two-column mode."""
    resolver = BoundaryResolver()
    markers = [
        QuestionMarker(number=str(i), page_index=1, normalized_point=(0.05, 0.10 + i * 0.05))
        for i in range(1, 10)
    ]
    # Add 1 stray marker on the far right (like an option fraction denominator)
    markers.append(QuestionMarker(number="12", page_index=1, normalized_point=(0.86, 0.10)))

    questions = resolver.resolve_page_questions(markers, page_index=1)
    # Must NOT be two-column: content width must be full single-column (~0.92)
    for q in questions:
        seg = q.segments[0]
        width = seg.normalized_bbox[2] - seg.normalized_bbox[0]
        assert width >= 0.90, f"Question {q.display_number} was cut in half to width {width}"


def test_boundary_resolver_large_question_full_width_protection():
    """Ensure large questions (大题) expand to full width if no neighbor shares vertical space."""
    resolver = BoundaryResolver()
    # 2 small questions in two columns at top, 1 large question at bottom
    markers = [
        QuestionMarker(number="1", page_index=0, normalized_point=(0.05, 0.10), question_type=QuestionType.SMALL),
        QuestionMarker(number="2", page_index=0, normalized_point=(0.05, 0.25), question_type=QuestionType.SMALL),
        QuestionMarker(number="3", page_index=0, normalized_point=(0.55, 0.10), question_type=QuestionType.SMALL),
        QuestionMarker(number="4", page_index=0, normalized_point=(0.55, 0.25), question_type=QuestionType.SMALL),
        QuestionMarker(number="15", page_index=0, normalized_point=(0.05, 0.50), question_type=QuestionType.LARGE),
    ]

    questions = resolver.resolve_page_questions(markers, page_index=0)
    q15 = next(q for q in questions if q.display_number == "15")
    q15_seg = q15.segments[0]
    width = q15_seg.normalized_bbox[2] - q15_seg.normalized_bbox[0]
    assert width >= 0.90, f"Q15 was cut in half: width={width}"


def test_boundary_resolver_near_bottom_safety():
    """Ensure marker near page bottom (y >= 0.98) never triggers y1 >= y2 ValidationError."""
    resolver = BoundaryResolver()
    markers = [
        QuestionMarker(number="21", page_index=1, normalized_point=(0.05, 0.85)),
        QuestionMarker(number="22", page_index=1, normalized_point=(0.05, 0.982)),
    ]

    questions = resolver.resolve_page_questions(markers, page_index=1)
    assert len(questions) == 2
    for q in questions:
        seg = q.segments[0]
        assert seg.normalized_bbox[1] < seg.normalized_bbox[3]
        assert 0.0 <= seg.normalized_bbox[1] <= 1.0
        assert 0.0 <= seg.normalized_bbox[3] <= 1.0


