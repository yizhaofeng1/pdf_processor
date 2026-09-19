"""Local Consistency Checker for Exam Questions and Segments.

Implements Design Doc Section 12:
- 12.1 Coordinate Range Check
- 12.2 Number Sequence Continuity Check
- 12.3 Overlap & Collision Check
- 12.5 Suspicious Area Check
"""

from typing import List
import logging

from ..models.question import Question, QuestionStatus
from ..pdf.coordinate import calculate_iou, calculate_overlap_ratio

logger = logging.getLogger("examsplit.detection.consistency")


class ConsistencyChecker:
    """Validates structural integrity, number continuity, and geometric consistency."""

    def __init__(
        self,
        min_segment_height: float = 0.02,
        min_segment_width: float = 0.05,
        min_segment_area: float = 0.005,
        max_iou_threshold: float = 0.05,
    ) -> None:
        self.min_segment_height = min_segment_height
        self.min_segment_width = min_segment_width
        self.min_segment_area = min_segment_area
        self.max_iou_threshold = max_iou_threshold

    def check(self, questions: List[Question]) -> List[Question]:
        """Perform comprehensive consistency checks on question list and annotate issues."""
        self._check_coordinate_ranges(questions)
        self._check_number_sequence(questions)
        self._check_segment_overlaps(questions)
        self._check_suspicious_areas(questions)

        # Update status if review required
        for q in questions:
            if q.review_required:
                q.status = QuestionStatus.REVIEW_REQUIRED
            elif q.status == QuestionStatus.DETECTED:
                q.status = QuestionStatus.VALIDATED

        return questions

    def _check_coordinate_ranges(self, questions: List[Question]) -> None:
        """Validate that all segment coordinates lie strictly in [0.0, 1.0]."""
        for q in questions:
            for seg in q.segments:
                x1, y1, x2, y2 = seg.normalized_bbox
                if not (0.0 <= x1 < x2 <= 1.0) or not (0.0 <= y1 < y2 <= 1.0):
                    q.review_required = True
                    if "INVALID_COORDINATES" not in q.reason_codes:
                        q.reason_codes.append("INVALID_COORDINATES")

                h = y2 - y1
                w = x2 - x1
                if h < self.min_segment_height or w < self.min_segment_width:
                    q.review_required = True
                    if "SEGMENT_TOO_SMALL" not in q.reason_codes:
                        q.reason_codes.append("SEGMENT_TOO_SMALL")

    def _check_number_sequence(self, questions: List[Question]) -> None:
        """Check for missing or duplicate question numbers."""
        seen_numbers: set[int] = set()
        int_numbers: list[int] = []

        for q in questions:
            try:
                num = int(q.display_number)
                if num in seen_numbers:
                    q.review_required = True
                    if "DUPLICATE_QUESTION_NUMBER" not in q.reason_codes:
                        q.reason_codes.append("DUPLICATE_QUESTION_NUMBER")
                seen_numbers.add(num)
                int_numbers.append(num)
            except ValueError:
                # E.g. section headers or lettered questions
                continue

        if len(int_numbers) >= 2:
            sorted_nums = sorted(int_numbers)
            min_num = sorted_nums[0]
            max_num = sorted_nums[-1]

            missing = set(range(min_num, max_num + 1)) - seen_numbers
            if missing:
                missing_str = ", ".join(str(m) for m in sorted(missing)[:5])
                logger.warning(f"Detected missing question numbers in sequence: {missing_str}")
                for q in questions:
                    try:
                        num = int(q.display_number)
                        # Flag questions directly bordering the missing gap
                        if num + 1 in missing or num - 1 in missing:
                            if "MISSING_QUESTION_NUMBER" not in q.reason_codes:
                                q.reason_codes.append("MISSING_QUESTION_NUMBER")
                                q.review_required = True
                    except ValueError:
                        pass

    def _check_segment_overlaps(self, questions: List[Question]) -> None:
        """Check for mutual bounding box collisions between segments on the same page."""
        # Collect all segments mapped to questions
        page_segs: dict[int, list[tuple[Question, any]]] = {}
        for q in questions:
            for seg in q.segments:
                page_segs.setdefault(seg.page_index, []).append((q, seg))

        for p_idx, seg_list in page_segs.items():
            n = len(seg_list)
            for i in range(n):
                q1, seg1 = seg_list[i]
                for j in range(i + 1, n):
                    q2, seg2 = seg_list[j]
                    if q1.id == q2.id:
                        continue

                    iou = calculate_iou(seg1.normalized_bbox, seg2.normalized_bbox)
                    overlap = calculate_overlap_ratio(seg1.normalized_bbox, seg2.normalized_bbox)

                    if iou > self.max_iou_threshold or overlap > 0.15:
                        q1.review_required = True
                        q2.review_required = True
                        if "OVERLAP_DETECTED" not in q1.reason_codes:
                            q1.reason_codes.append("OVERLAP_DETECTED")
                        if "OVERLAP_DETECTED" not in q2.reason_codes:
                            q2.reason_codes.append("OVERLAP_DETECTED")

    def _check_suspicious_areas(self, questions: List[Question]) -> None:
        """Check if any segment is suspiciously small or overwhelmingly large."""
        for q in questions:
            for seg in q.segments:
                x1, y1, x2, y2 = seg.normalized_bbox
                area = (x2 - x1) * (y2 - y1)
                if area < self.min_segment_area:
                    q.review_required = True
                    if "SUSPICIOUS_AREA" not in q.reason_codes:
                        q.reason_codes.append("SUSPICIOUS_AREA")
