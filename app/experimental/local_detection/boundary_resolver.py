"""Deterministic boundary resolution, padding application, and blank trimming.

Implements coordinate clamping, safety padding, option enclosing protection,
large question full-width adaptation, and empty answer space trimming.
"""

from typing import List, Tuple
from ..local_ai.config import LocalModelConfig
from ..local_ai.types import LocalQuestionCandidate


class LocalBoundaryResolver:
    """Calculates final polished bounding boxes for candidates."""

    def __init__(self, config: LocalModelConfig) -> None:
        self.config = config

    def resolve_candidates(
        self,
        candidates: List[LocalQuestionCandidate],
        is_two_column: bool = False,
        split_x: float = 0.50,
    ) -> List[LocalQuestionCandidate]:
        """Resolve and refine boundaries for all candidates on a page."""
        if not candidates:
            return []

        # 1. Apply safety padding and rule-based adjustments
        for c in candidates:
            if not c.segments:
                continue

            q_num = int(c.question_number) if c.question_number.isdigit() else 0
            is_large_q = q_num >= 15 or c.question_type == "solution"

            new_segments = []
            for seg in c.segments:
                x0, y0, x1, y1 = seg.bbox

                # Apply safety padding
                x0 = max(0.0, x0 - self.config.pad_ratio_x)
                y0 = max(0.0, y0 - self.config.pad_ratio_y)
                x1 = min(1.0, x1 + self.config.pad_ratio_x)
                y1 = min(1.0, y1 + self.config.pad_ratio_y)

                # Large question rule: expand to full width if not strictly confined to a column
                if is_large_q and (x1 - x0) > 0.40:
                    x0 = min(x0, 0.045)
                    x1 = max(x1, 0.955)

                # Ensure minimum height & width
                if y1 <= y0:
                    y1 = min(1.0, y0 + 0.030)
                if x1 <= x0:
                    x1 = min(1.0, x0 + 0.050)

                seg.bbox = (round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4))
                new_segments.append(seg)

            c.segments = new_segments

        # 2. Prevent overlap between consecutive questions in the same column
        self._prevent_consecutive_overlap(candidates, is_two_column, split_x)

        return candidates

    def _prevent_consecutive_overlap(
        self,
        candidates: List[LocalQuestionCandidate],
        is_two_column: bool,
        split_x: float,
    ) -> None:
        """Ensure no vertical collision between consecutive question bounding boxes."""
        # Sort candidates by top-y
        sorted_cand = sorted(candidates, key=lambda c: c.segments[0].bbox[1] if c.segments else 0.0)

        for i in range(len(sorted_cand) - 1):
            curr = sorted_cand[i]
            nxt = sorted_cand[i + 1]
            if not curr.segments or not nxt.segments:
                continue

            curr_seg = curr.segments[0]
            nxt_seg = nxt.segments[0]

            # Check if they share the same column or horizontally overlap
            h_overlap = not (curr_seg.bbox[2] <= nxt_seg.bbox[0] or curr_seg.bbox[0] >= nxt_seg.bbox[2])
            if h_overlap:
                curr_y1 = curr_seg.bbox[3]
                nxt_y0 = nxt_seg.bbox[1]
                if curr_y1 > nxt_y0:
                    # Resolve collision: cut current bottom slightly before next top
                    safe_bottom = max(curr_seg.bbox[1] + 0.02, nxt_y0 - 0.005)
                    curr_seg.bbox = (
                        curr_seg.bbox[0],
                        curr_seg.bbox[1],
                        curr_seg.bbox[2],
                        round(safe_bottom, 4),
                    )
