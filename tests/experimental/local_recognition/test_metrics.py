"""Unit tests for MetricsCalculator and Summary Report Generation."""

from app.experimental.local_recognition.types import RefinedQuestionSegment, ExperimentRun
from app.experimental.local_recognition.metrics import MetricsCalculator


def test_metrics_computation_without_reference():
    segs = [
        RefinedQuestionSegment(
            question_number="1",
            page_index=0,
            normalized_bbox=(0.05, 0.1, 0.95, 0.3),
            pdf_bbox=(30.0, 80.0, 560.0, 250.0),
        ),
        RefinedQuestionSegment(
            question_number="2",
            page_index=0,
            normalized_bbox=(0.05, 0.35, 0.95, 0.6),
            pdf_bbox=(30.0, 280.0, 560.0, 500.0),
        ),
    ]

    metrics = MetricsCalculator.compute_metrics(
        detected_segments=segs,
        coarse_calls=1,
        local_calls=2,
        latency_seconds=4.25,
        input_image_count=3,
        input_image_pixels=3000000,
    )

    assert metrics.total_questions_detected == 2
    assert metrics.coarse_calls == 1
    assert metrics.local_calls == 2
    assert metrics.total_calls == 3
    assert metrics.latency_seconds == 4.25
    assert metrics.question_precision is None
    assert metrics.estimated_tokens is None


def test_metrics_computation_with_reference():
    segs = [
        RefinedQuestionSegment(
            question_number="1",
            page_index=0,
            normalized_bbox=(0.1, 0.1, 0.9, 0.3),
            pdf_bbox=(60.0, 80.0, 540.0, 250.0),
        ),
        RefinedQuestionSegment(
            question_number="2",
            page_index=0,
            normalized_bbox=(0.1, 0.4, 0.9, 0.8),
            pdf_bbox=(60.0, 320.0, 540.0, 640.0),
        ),
    ]

    reference = [
        {"question_number": "1", "normalized_bbox": (0.1, 0.1, 0.9, 0.3)},  # Perfect match
        {"question_number": "2", "normalized_bbox": (0.1, 0.4, 0.9, 0.8)},  # Perfect match
        {"question_number": "3", "normalized_bbox": (0.1, 0.8, 0.9, 0.95)}, # Missed in det
    ]

    metrics = MetricsCalculator.compute_metrics(
        detected_segments=segs,
        reference_segments=reference,
    )

    # Det: 2, Ref: 3, True Positives: 2
    assert metrics.question_precision == 1.0  # 2 / 2
    assert abs(metrics.question_recall - (2 / 3)) < 1e-3
    assert metrics.mean_boundary_iou == 1.0
    assert metrics.missed_question_count == 1


def test_generate_summary_markdown():
    run = ExperimentRun(
        run_id="test_run_001",
        source_pdf_name="sample_exam.pdf",
        source_pdf_hash="abcdef1234567890",
        model_name="qwen2.5-vl",
        mode="virtual_address",
        grid_rows=8,
        grid_columns=4,
    )

    metrics = MetricsCalculator.compute_metrics(
        detected_segments=[],
        coarse_calls=1,
        local_calls=4,
        latency_seconds=3.14,
    )

    md = MetricsCalculator.generate_summary_markdown(run, metrics)
    assert "test_run_001" in md
    assert "qwen2.5-vl" in md
    assert "8 × 4" in md
    assert "3.14 s" in md
