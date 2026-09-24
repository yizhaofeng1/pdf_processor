"""Reading order determination and column structure analysis.

Ensures proper reading order for multi-column and single-column exam papers,
avoiding cross-column reading interleaving.
"""

from typing import Any, List, Optional, Tuple


class ReadingOrderDetector:
    """Analyzes page column distribution and sorts blocks/elements in reading order."""

    def __init__(self, gutter_min_x: float = 0.44, gutter_max_x: float = 0.56) -> None:
        self.gutter_min_x = gutter_min_x
        self.gutter_max_x = gutter_max_x

    def detect_two_column(
        self,
        elements: List[Any],
        markers: Optional[List[Any]] = None,
    ) -> Tuple[bool, Optional[float]]:
        """Detect if the page has a two-column layout.
        
        Args:
            elements: List of objects with a .bbox attribute (x1, y1, x2, y2).
            markers: Optional list of QuestionMarker objects for ground-truth column validation.
            
        Returns:
            Tuple of (is_two_column: bool, split_x: Optional[float]).
        """
        # If question markers are available, they provide unambiguous evidence of question column layout
        if markers:
            q_markers = [m for m in markers if not getattr(m, "is_section_header", False)]
            if q_markers:
                left_markers = [m for m in q_markers if (m.bbox[0] + m.bbox[2]) / 2 < 0.48]
                right_markers = [m for m in q_markers if (m.bbox[0] + m.bbox[2]) / 2 >= 0.48]
                # A genuine two-column exam layout requires questions flowing down both columns
                if len(right_markers) < 2:
                    return False, None
                if len(left_markers) >= 2 and len(right_markers) >= 2:
                    return True, 0.50

        # Heuristic check on text elements
        body_elements = [
            e for e in elements
            if getattr(e, "bbox", None) is not None
            and e.bbox[1] > 0.08  # below top header
            and e.bbox[3] < 0.93  # above bottom footer
            and (e.bbox[2] - e.bbox[0]) < 0.75  # not full-width
        ]

        if len(body_elements) < 6:
            return False, None

        left_starts = 0
        right_starts = 0
        mid_count = 0

        for e in body_elements:
            x1, _, x2, _ = e.bbox
            if x1 < 0.48 and x2 > 0.52:
                mid_count += 1
            elif x1 < 0.25:
                left_starts += 1
            elif 0.50 <= x1 <= 0.70:
                right_starts += 1

        total = len(body_elements)
        # Two-column layout requires substantial line beginnings on the right column margin (0.50~0.70)
        # and virtually no text bridging the central gutter ([0.48, 0.52])
        if left_starts >= 3 and right_starts >= 3 and (mid_count / total) < 0.05:
            return True, 0.50

        return False, None

    def sort_in_reading_order(self, elements: List[Any]) -> List[Any]:
        """Sort elements in deterministic visual reading order."""
        if not elements:
            return []

        is_two_col, split_x = self.detect_two_column(elements)
        split = split_x or 0.50

        if not is_two_col:
            # Single-column: sort top-to-bottom, left-to-right with tolerance band
            return sorted(elements, key=lambda e: (round(e.bbox[1], 2), e.bbox[0]))

        # Two-column layout
        headers: List[Any] = []
        left_col: List[Any] = []
        right_col: List[Any] = []
        footers: List[Any] = []

        for e in elements:
            x1, y1, x2, y2 = e.bbox
            # Header
            if y2 <= 0.08 or (x1 < 0.2 and x2 > 0.8 and y1 < 0.15):
                headers.append(e)
            # Footer
            elif y1 >= 0.93 or (x1 < 0.2 and x2 > 0.8 and y2 > 0.90):
                footers.append(e)
            # Full width section header in body
            elif x1 < 0.25 and x2 > 0.75:
                left_col.append(e)
            # Left column
            elif (x1 + x2) / 2 < split:
                left_col.append(e)
            # Right column
            else:
                right_col.append(e)

        # Sort each partition
        headers.sort(key=lambda e: (round(e.bbox[1], 2), e.bbox[0]))
        left_col.sort(key=lambda e: (round(e.bbox[1], 2), e.bbox[0]))
        right_col.sort(key=lambda e: (round(e.bbox[1], 2), e.bbox[0]))
        footers.sort(key=lambda e: (round(e.bbox[1], 2), e.bbox[0]))

        return headers + left_col + right_col + footers


def sort_elements_reading_order(elements: List[Any]) -> List[Any]:
    """Helper to sort any list of bbox-bearing items in reading order."""
    detector = ReadingOrderDetector()
    return detector.sort_in_reading_order(elements)
