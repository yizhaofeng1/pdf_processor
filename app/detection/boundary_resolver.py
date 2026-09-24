"""Boundary Resolver: Converts question marker anchors into bounded visual segments.

Follows the 'Anchor First, Boundary Second' principle and supports both
single-column and two-column page layouts.
"""

from typing import List, Tuple, Optional, Any
import uuid
import re
import logging


from .marker_detector import QuestionMarker
from ..models.question import Question, QuestionType, QuestionStatus, AnchorPoint
from ..models.segment import QuestionSegment
from ..pdf.coordinate import clamp, add_padding

logger = logging.getLogger("examsplit.detection.boundary")


class BoundaryResolver:
    """Derives bounded rectangular segments from question markers on a page."""

    def __init__(
        self,
        default_left_margin: float = 0.04,
        default_right_margin: float = 0.96,
        top_safety_margin: float = 0.01,
        bottom_safety_margin: float = 0.006,
        page_bottom_limit: float = 0.95,
        column_split_threshold: float = 0.50,
    ) -> None:
        self.default_left_margin = default_left_margin
        self.default_right_margin = default_right_margin
        self.top_safety_margin = top_safety_margin
        self.bottom_safety_margin = bottom_safety_margin
        self.page_bottom_limit = page_bottom_limit
        self.column_split_threshold = column_split_threshold

    def resolve_page_questions(
        self,
        markers: List[QuestionMarker],
        page_index: int,
        page_width: float = 595.0,
        page_height: float = 842.0,
        text_blocks: Optional[List[tuple]] = None,
    ) -> List[Question]:
        """Convert a list of markers on a page into structured Question domain models with text bounds snapping."""
        if not markers:
            return []

        # 1. Detect if two-column layout
        is_two_column = self._detect_two_column(markers)

        if is_two_column:
            left_markers = [m for m in markers if m.normalized_point[0] < self.column_split_threshold]
            right_markers = [m for m in markers if m.normalized_point[0] >= self.column_split_threshold]

            left_markers.sort(key=lambda m: m.normalized_point[1])
            right_markers.sort(key=lambda m: m.normalized_point[1])

            left_questions = self._resolve_column(
                left_markers,
                page_index,
                x_left=self.default_left_margin,
                x_right=self.column_split_threshold - 0.015,
            )
            right_questions = self._resolve_column(
                right_markers,
                page_index,
                x_left=self.column_split_threshold + 0.015,
                x_right=self.default_right_margin,
            )
            raw_questions = left_questions + right_questions

            # Post-process: Expand Large Questions (大题) to full page width if they have no horizontal neighbor
            for q in raw_questions:
                if self._is_large_question(q) and q.segments:
                    q_seg = q.segments[0]
                    qy1, qy2 = q_seg.normalized_bbox[1], q_seg.normalized_bbox[3]
                    has_neighbor = any(
                        other.id != q.id
                        and other.segments
                        and other.segments[0].page_index == page_index
                        and not (
                            other.segments[0].normalized_bbox[3] <= qy1 + 0.01
                            or other.segments[0].normalized_bbox[1] >= qy2 - 0.01
                        )
                        for other in raw_questions
                    )
                    if not has_neighbor:
                        q_seg.normalized_bbox = (
                            self.default_left_margin,
                            q_seg.normalized_bbox[1],
                            self.default_right_margin,
                            q_seg.normalized_bbox[3],
                        )
        else:
            sorted_markers = sorted(markers, key=lambda m: m.normalized_point[1])
            raw_questions = self._resolve_column(
                sorted_markers,
                page_index,
                x_left=self.default_left_margin,
                x_right=self.default_right_margin,
            )

        # 2. If vector text blocks exist, perform micro boundary snapping
        if text_blocks and page_width > 0 and page_height > 0:
            return self._snap_questions_to_text_blocks(raw_questions, text_blocks, page_width, page_height)

        return raw_questions

    def _detect_two_column(self, markers: List[QuestionMarker]) -> bool:
        """Heuristic to detect if questions are arranged in two columns.
        
        Requires:
        1. At least 4 markers on the page.
        2. At least 2 markers in the left column (x < split_threshold - 0.05).
        3. At least 2 markers in the right column within normal column bounds (split_threshold - 0.05 <= x <= 0.70).
        4. Right-column markers must make up at least 25% of total markers.
        """
        if len(markers) < 4:
            return False

        left_markers = [m for m in markers if m.normalized_point[0] < self.column_split_threshold - 0.05]
        right_markers = [
            m for m in markers
            if self.column_split_threshold - 0.05 <= m.normalized_point[0] <= 0.70
        ]
        if len(left_markers) < 2 or len(right_markers) < 2:
            return False

        if (len(right_markers) / len(markers)) < 0.25:
            return False

        return True

    def _is_large_question(self, q_or_marker: Any) -> bool:
        """Determine whether a question is a large question (大题).

        AI explicitly outputs '大题' or '小题'.
        - If '大题' (or solve/proof/large): local interval constraints on y2 are applied
          to eliminate exaggerated blank answer space, while keeping y1 fixed at the question start.
        - If '小题' (or choice/fill_in/small): the AI's visual bounding box is trusted directly.
        """
        q_type = getattr(q_or_marker, "question_type", None)
        if q_type:
            t_str = str(q_type).strip()
            if "大" in t_str or t_str.lower() in ("solve", "proof", "large"):
                return True
            if "小" in t_str or t_str.lower() in ("choice", "fill_in", "small"):
                return False

        num_val = getattr(q_or_marker, "display_number", getattr(q_or_marker, "number", ""))
        try:
            num = int(re.sub(r"[^\d]", "", str(num_val)))
            if num >= 15:
                return True
            if 1 <= num <= 14:
                return False
        except ValueError:
            pass

        return False

    def _is_dense_small_question(self, q_or_marker: Any, total_questions_on_page: int = 0) -> bool:
        """Backward compatibility alias: inverse of _is_large_question."""
        return not self._is_large_question(q_or_marker)


    def _resolve_column(
        self,
        markers: List[QuestionMarker],
        page_index: int,
        x_left: float,
        x_right: float,
    ) -> List[Question]:
        """Derive vertical question segments within a single column with strict non-overlapping bounds."""
        questions: List[Question] = []
        n = len(markers)
        prev_end_y = 0.01

        for i, marker in enumerate(markers):
            # 1. Clean display number: strip parentheses "(17)" -> "17"
            clean_num = re.sub(r"[^\d]", "", str(marker.number)) if any(c.isdigit() for c in str(marker.number)) else str(marker.number)
            if not clean_num:
                clean_num = str(marker.number)

            curr_y = marker.normalized_point[1]
            if marker.normalized_bbox and marker.normalized_bbox[1] > 0:
                curr_y = min(curr_y, marker.normalized_bbox[1])

            y1_default = clamp(curr_y - self.top_safety_margin, 0.01, 0.98)
            if i > 0:
                y1_default = max(y1_default, prev_end_y + 0.002)

            # Max allowed bottom boundary: STRICTLY must not invade next marker start
            if i + 1 < n:
                next_marker_y = markers[i + 1].normalized_point[1]
                if markers[i + 1].normalized_bbox and markers[i + 1].normalized_bbox[1] > 0:
                    next_start = min(next_marker_y, markers[i + 1].normalized_bbox[1])
                else:
                    next_start = next_marker_y
                max_allowed_y2 = clamp(next_start - self.bottom_safety_margin, y1_default + 0.015, 0.99)
            else:
                is_sub_column = (x_right - x_left) < 0.60
                if is_sub_column and not self._is_large_question(marker):
                    # In a multi-column sub-column, an isolated small question shouldn't swallow the whole page
                    max_allowed_y2 = min(self.page_bottom_limit, y1_default + 0.25)
                else:
                    max_allowed_y2 = max(self.page_bottom_limit, min(0.99, y1_default + 0.03))
                max_allowed_y2 = max(max_allowed_y2, min(0.99, y1_default + 0.02))

            # If marker already came with a pre-validated AI bbox, prioritize and validate it
            if marker.normalized_bbox and len(marker.normalized_bbox) == 4:
                bx1, by1, bx2, by2 = marker.normalized_bbox
                bx1 = clamp(bx1, 0.0, 1.0)
                by1 = clamp(by1, 0.0, 1.0)
                bx2 = clamp(bx2, 0.0, 1.0)
                by2 = clamp(by2, 0.0, 1.0)

                # Single-column width normalization: ensure box spans the full page content width
                if abs((x_right - x_left) - (self.default_right_margin - self.default_left_margin)) < 0.05:
                    bx1 = x_left
                    bx2 = x_right

                # CRITICAL: by2 MUST NOT exceed the next question's top boundary!
                if i + 1 < n:
                    by2 = min(by2, max_allowed_y2)

                if i > 0:
                    by1 = max(by1, prev_end_y + 0.002)

                if bx1 < bx2 and by1 < by2 and (by2 - by1) >= 0.015:
                    bbox = (bx1, by1, bx2, by2)
                else:
                    bbox = (x_left, y1_default, x_right, max_allowed_y2)
            else:
                bbox = (x_left, y1_default, x_right, max_allowed_y2)

            # Mathematical validation: strictly guarantee x1 < x2 and y1 < y2 in [0.0, 1.0]
            final_x1 = clamp(bbox[0], 0.0, 0.97)
            final_x2 = clamp(bbox[2], final_x1 + 0.02, 1.0)
            final_y1 = clamp(bbox[1], 0.0, 0.98)
            final_y2 = clamp(bbox[3], final_y1 + 0.015, 1.0)
            bbox = (final_x1, final_y1, final_x2, final_y2)

            prev_end_y = bbox[3]

            q_id = str(uuid.uuid4())
            seg = QuestionSegment(
                question_id=q_id,
                page_index=page_index,
                normalized_bbox=bbox,
            )

            q = Question(
                id=q_id,
                display_number=clean_num,
                question_type=marker.question_type,
                segments=[seg],
                start_anchor=AnchorPoint(
                    page_index=page_index,
                    normalized_point=marker.normalized_point,
                ),
                confidence=marker.confidence,
                sort_order=i,
                status=QuestionStatus.DETECTED,
            )
            questions.append(q)

        return questions

    def _calculate_derived_bbox(
        self,
        markers: List[QuestionMarker],
        i: int,
        x_left: float,
        x_right: float,
    ) -> Tuple[float, float, float, float]:
        """Derive vertical bounds [y1, y2] from marker anchors."""
        curr_m = markers[i]
        curr_y = curr_m.normalized_point[1]

        y1 = clamp(curr_y - self.top_safety_margin, 0.02, 0.98)

        if i + 1 < len(markers):
            next_y = markers[i + 1].normalized_point[1]
            y2 = clamp(next_y - self.bottom_safety_margin, y1 + 0.02, 0.98)
        else:
            y2 = self.page_bottom_limit

        if y2 <= y1:
            y2 = min(1.0, y1 + 0.05)

        return (x_left, y1, x_right, y2)

    def _is_dense_large_question(
        self,
        q: Question,
        sorted_qs: List[Question],
        curr_idx: int,
        next_limit_y: float,
    ) -> bool:
        """Check if AI returned an already dense large question interval on this page.

        If the AI's returned interval is compact (e.g., height <= 0.35), or if multiple
        large questions share the page with compact intervals (average distance <= 0.38),
        or the gap between the AI box end and the next question start is small (<= 0.08),
        this indicates the source test paper is dense with calculation/proof questions.
        In this case, trust the AI visual boundary and prohibit local downward expansions.
        """
        if not q.segments:
            return False
        seg = q.segments[0]
        qy1, qy2 = seg.normalized_bbox[1], seg.normalized_bbox[3]
        ai_height = qy2 - qy1

        # 1. Very compact height directly returned by AI (e.g. <= 0.22, short solve question)
        if ai_height <= 0.22:
            return True

        # 2. In multi-question context (dense question paper):
        if len(sorted_qs) >= 2:
            # Compact height when multiple questions share page
            if ai_height <= 0.30:
                return True
            # Gap to next question is small (compact vertical flow)
            if next_limit_y < 0.95 and (next_limit_y - qy2) <= 0.08:
                return True
            # Multiple large questions on the same page/column
            large_qs_count = sum(1 for item in sorted_qs if self._is_large_question(item))
            if large_qs_count >= 2 and (next_limit_y - qy1) <= 0.45:
                return True

        return False

    def _snap_questions_to_text_blocks(
        self,
        questions: List[Question],
        text_blocks: List[tuple],
        page_w: float,
        page_h: float,
    ) -> List[Question]:
        """Refine bounding box bounds: trust AI for dense questions, review sparse large solve questions.

        - Small questions (choice/fill-in) & Dense Large questions: Trust AI's visual bounding box directly!
          The AI sees the visual ink boundaries. Do NOT run aggressive local text expansion.
        - Sparse Large questions (解答题/证明题伴随大片空白): Apply strict local review to find the actual
          end of black text and lop off any exaggerated blank answer space.
        """
        if not questions or not text_blocks:
            return questions

        # Normalize text blocks: (x0, y0, x1, y1, text)
        norm_blocks = []
        for b in text_blocks:
            if len(b) >= 5 and b[6] == 0:
                text = b[4].strip()
                if text and not text.startswith("—"):
                    bx0 = clamp(b[0] / page_w, 0.0, 1.0)
                    by0 = clamp(b[1] / page_h, 0.0, 1.0)
                    bx1 = clamp(b[2] / page_w, 0.0, 1.0)
                    by1 = clamp(b[3] / page_h, 0.0, 1.0)
                    norm_blocks.append((bx0, by0, bx1, by1, text))

        if not norm_blocks:
            return questions

        # Sort questions vertically by top y
        sorted_qs = sorted(questions, key=lambda q: q.segments[0].normalized_bbox[1] if q.segments else 0.0)

        for i, q in enumerate(sorted_qs):
            if not q.segments:
                continue
            seg = q.segments[0]
            qx1, qy1, qx2, qy2 = seg.normalized_bbox

            # Next question's anchor or top boundary
            next_limit_y = self.page_bottom_limit
            if i + 1 < len(sorted_qs):
                next_q = sorted_qs[i + 1]
                next_seg = next_q.segments[0]
                if not (qx2 < next_seg.normalized_bbox[0] or qx1 > next_seg.normalized_bbox[2]):
                    anchor_y = next_q.start_anchor.normalized_point[1] if next_q.start_anchor else next_seg.normalized_bbox[1]
                    next_limit_y = min(anchor_y, next_seg.normalized_bbox[1])

            prev_limit_y = 0.01
            if i > 0:
                prev_q = sorted_qs[i - 1]
                prev_seg = prev_q.segments[0]
                if not (qx2 < prev_seg.normalized_bbox[0] or qx1 > prev_seg.normalized_bbox[2]):
                    prev_limit_y = prev_seg.normalized_bbox[3]

            is_large = self._is_large_question(q)

            if not is_large:
                # ----------------------------------------------------
                # 小题（以 AI 视觉为准）：
                # 纯粹信任 AI 的视觉边界框，绝不做本地文本吸附拉扯。
                # 仅做基础防重叠区间约束。
                # ----------------------------------------------------
                if i > 0:
                    qy1 = max(qy1, prev_limit_y + 0.002)
                if i + 1 < len(sorted_qs):
                    qy2 = min(qy2, next_limit_y - 0.002)
                if qy2 <= qy1 + 0.01:
                    qy2 = min(next_limit_y - 0.002, qy1 + 0.015)
            else:
                # ----------------------------------------------------
                # 大题处理：
                # 检测是否属于密集大题排版。如果 AI 返回的大题区间本来就比较密集，
                # 说明源文件本身就是大题密集的，以 AI 为主，禁止本地做任何向下扩展！
                # ----------------------------------------------------
                if i > 0:
                    qy1 = max(qy1, prev_limit_y + 0.002)

                is_dense_large = self._is_dense_large_question(q, sorted_qs, i, next_limit_y)

                if is_dense_large:
                    # 密集大题：纯粹以 AI 视觉为准！严禁本地向下扩展吸附
                    if i + 1 < len(sorted_qs):
                        qy2 = min(qy2, next_limit_y - 0.002)
                    if qy2 <= qy1 + 0.01:
                        qy2 = min(next_limit_y - 0.002, qy1 + 0.015)
                    logger.debug(f"Question {q.display_number}: 判定为密集大题，以 AI 视觉边界为主，禁止本地扩展。")
                else:
                    # 稀疏大题（可能有大片空白作答区）：
                    # 本地只对稀疏大题做区间约束，剔除夸大空白：
                    # y2 本地严格审查：依据本题实际文字/公式结尾紧贴闭合
                    q_blocks = [
                        b for b in norm_blocks
                        if (b[3] >= (qy1 - 0.005))
                        and (b[1] < (next_limit_y - 0.005))
                        and not (b[2] < qx1 - 0.05 or b[0] > qx2 + 0.05)
                    ]
                    if q_blocks:
                        last_text_bottom = max(b[3] for b in q_blocks)
                        max_allowed_bottom = min(next_limit_y - 0.005, last_text_bottom + 0.012)
                        qy2 = min(max(qy2, last_text_bottom + 0.004), max_allowed_bottom)
                    else:
                        if i + 1 < len(sorted_qs):
                            qy2 = min(qy2, next_limit_y - 0.005)

            qy1 = clamp(qy1, 0.01, 0.98)
            qy2 = clamp(qy2, qy1 + 0.015, 0.99)
            seg.normalized_bbox = (qx1, qy1, qx2, qy2)

        return sorted_qs


