"""Metrics computation and summary report generation for VAQL experiments."""

from typing import List, Dict, Optional, Any
from .types import ExperimentMetrics, RefinedQuestionSegment, ExperimentRun
from ...pdf.coordinate import calculate_iou


class MetricsCalculator:
    """Calculates benchmark metrics for question detection and boundary precision."""

    @staticmethod
    def compute_metrics(
        detected_segments: List[RefinedQuestionSegment],
        coarse_calls: int = 0,
        local_calls: int = 0,
        latency_seconds: float = 0.0,
        input_image_count: int = 0,
        input_image_pixels: int = 0,
        reference_segments: Optional[List[Dict[str, Any]]] = None,
    ) -> ExperimentMetrics:
        """Compute evaluation metrics, optionally comparing against a reference baseline or golden set."""
        total_detected = len(detected_segments)
        cross_pages = sum(1 for s in detected_segments if getattr(s, "cross_page", False))

        metrics = ExperimentMetrics(
            total_questions_detected=total_detected,
            cross_page_count=cross_pages,
            coarse_calls=coarse_calls,
            local_calls=local_calls,
            total_calls=coarse_calls + local_calls,
            latency_seconds=round(latency_seconds, 2),
            input_image_count=input_image_count,
            input_image_pixels=input_image_pixels,
            estimated_tokens=None,  # Not faked if local endpoint does not supply token stats
        )

        if not reference_segments:
            return metrics

        # Compute comparison metrics against reference
        ref_by_q = {str(r.get("question_number", "")): r for r in reference_segments}
        det_by_q = {str(s.question_number): s for s in detected_segments}

        true_positives = 0
        ious: List[float] = []

        for q_num, det in det_by_q.items():
            if q_num in ref_by_q:
                true_positives += 1
                ref_bbox = ref_by_q[q_num].get("normalized_bbox")
                if ref_bbox and len(ref_bbox) == 4:
                    iou = calculate_iou(det.normalized_bbox, tuple(ref_bbox))
                    ious.append(iou)

        det_count = len(det_by_q)
        ref_count = len(ref_by_q)

        metrics.question_precision = round(true_positives / max(1, det_count), 4)
        metrics.question_recall = round(true_positives / max(1, ref_count), 4)
        metrics.mean_boundary_iou = round(sum(ious) / max(1, len(ious)), 4) if ious else None
        metrics.missed_question_count = max(0, ref_count - true_positives)
        metrics.duplicate_question_count = max(0, total_detected - len(det_by_q))

        return metrics

    @staticmethod
    def generate_summary_markdown(run: ExperimentRun, metrics: ExperimentMetrics) -> str:
        """Generate human-readable Markdown summary report for this experiment run."""
        lines = [
            f"# VAQL Experiment Summary Report",
            f"",
            f"**Run ID:** `{run.run_id}`  ",
            f"**Timestamp:** `{run.start_time}` ~ `{run.end_time or 'N/A'}`  ",
            f"**Model:** `{run.model_name}` ({run.model_provider})  ",
            f"**Mode:** `{run.mode}`  ",
            f"**Grid:** `{run.grid_rows} × {run.grid_columns}`  ",
            f"**Source Document:** `{run.source_pdf_name}` (`{run.source_pdf_hash[:12]}...`)  ",
            f"",
            f"---",
            f"",
            f"## 1. Detection Performance",
            f"",
            f"| Metric | Value |",
            f"| :--- | :--- |",
            f"| **Total Detected** | {metrics.total_questions_detected} |",
            f"| **Precision** | {f'{metrics.question_precision * 100:.1f}%' if metrics.question_precision is not None else 'N/A'} |",
            f"| **Recall** | {f'{metrics.question_recall * 100:.1f}%' if metrics.question_recall is not None else 'N/A'} |",
            f"| **Mean Boundary IoU** | {f'{metrics.mean_boundary_iou:.4f}' if metrics.mean_boundary_iou is not None else 'N/A'} |",
            f"| **Cross-page Questions** | {metrics.cross_page_count} |",
            f"| **Missed Count** | {metrics.missed_question_count} |",
            f"| **Duplicate Count** | {metrics.duplicate_question_count} |",
            f"",
            f"## 2. Resource & Cost Metrics",
            f"",
            f"| Metric | Value |",
            f"| :--- | :--- |",
            f"| **Coarse Calls** | {metrics.coarse_calls} |",
            f"| **Local Refine Calls** | {metrics.local_calls} |",
            f"| **Total Model Calls** | {metrics.total_calls} |",
            f"| **Total Latency** | {metrics.latency_seconds:.2f} s |",
            f"| **Input Images** | {metrics.input_image_count} |",
            f"| **Input Pixels** | {metrics.input_image_pixels:,} |",
            f"| **Estimated Tokens** | {metrics.estimated_tokens if metrics.estimated_tokens is not None else 'N/A (Endpoint unmetered)'} |",
            f"",
            f"---",
            f"",
            f"*Generated by ExamSplit AI Local Recognition (VAQL) Experiment Module.*",
        ]
        return "\n".join(lines)
