"""Assembles question candidates by associating layout elements and text between markers.

Builds structured LocalQuestionCandidate instances containing associated
stem text, options (A-D), math formulas, and embedded figures.
"""

import re
from typing import Any, List, Optional, Set, Tuple
from ..local_ai.types import (
    CandidateSegment,
    LayoutElement,
    LocalQuestionCandidate,
    OCRBlock,
    QuestionMarker,
)
from .reading_order import ReadingOrderDetector


class LocalCandidateBuilder:
    """Groups elements and text blocks between markers into cohesive question candidates."""

    OPTION_REGEX = re.compile(r"[\(\[（]?[A-D][\)\]）\.\、]")

    def __init__(self) -> None:
        self.reading_order_detector = ReadingOrderDetector()

    def build_candidates_for_page(
        self,
        page_index: int,
        markers: List[QuestionMarker],
        layout_elements: List[LayoutElement],
        text_blocks: List[OCRBlock],
        is_two_column: bool = False,
        split_x: Optional[float] = None,
    ) -> List[LocalQuestionCandidate]:
        """Assemble question candidates for a single page."""
        # Separate question markers from section headers
        q_markers = [m for m in markers if not m.is_section_header]
        sec_markers = [m for m in markers if m.is_section_header]

        if not q_markers:
            return []

        # Sort markers in reading order
        all_ordered_markers = self.reading_order_detector.sort_in_reading_order(markers)
        split = split_x or 0.50

        candidates: List[LocalQuestionCandidate] = []

        for i, m in enumerate(q_markers):
            # Find the stopping marker after m in reading order
            next_marker = self._find_next_stopping_marker(m, all_ordered_markers)

            # Determine column of current marker
            m_col = "full" if not is_two_column else ("left" if (m.bbox[0] + m.bbox[2]) / 2 < split else "right")

            # Gather associated layout elements and text
            associated_elements = []
            associated_blocks = []

            for idx, elem in enumerate(layout_elements):
                if elem.category in ["header", "footer", "page_number"]:
                    continue

                if is_two_column and m_col != "full":
                    e_col = "left" if (elem.bbox[0] + elem.bbox[2]) / 2 < split else "right"
                    # If element is narrow and in other column, skip
                    if e_col != m_col and (elem.bbox[2] - elem.bbox[0]) < 0.65:
                        continue

                # Vertical span check
                y_start = m.bbox[1] - 0.012  # tolerance above marker top
                y_end = next_marker.bbox[1] if (next_marker and self._same_column(m, next_marker, is_two_column, split)) else 0.93

                if elem.bbox[1] >= y_start and elem.bbox[3] <= y_end + 0.015:
                    associated_elements.append((idx, elem))

            for blk in text_blocks:
                if is_two_column and m_col != "full":
                    b_col = "left" if (blk.bbox[0] + blk.bbox[2]) / 2 < split else "right"
                    if b_col != m_col and (blk.bbox[2] - blk.bbox[0]) < 0.65:
                        continue

                y_start = m.bbox[1] - 0.012
                y_end = next_marker.bbox[1] if (next_marker and self._same_column(m, next_marker, is_two_column, split)) else 0.93

                if blk.bbox[1] >= y_start and blk.bbox[3] <= y_end + 0.015:
                    associated_blocks.append(blk)

            # Inspect options (A, B, C, D)
            options_found = self._detect_options(associated_blocks)
            has_options = {"A", "B", "C", "D"}.issubset(set(options_found))
            
            # Infer question type
            q_num_int = int(m.number) if m.number.isdigit() else 0
            if has_options:
                q_type = "choice"
            elif q_num_int >= 15:
                q_type = "solution"
            elif any("填空" in (sec.raw_text or "") for sec in sec_markers if sec.bbox[1] < m.bbox[1]):
                q_type = "fill_blank"
            else:
                q_type = "unknown"

            # Compute preliminary segment bbox
            seg_bbox = self._calculate_initial_bbox(m, associated_elements, associated_blocks, is_two_column, m_col, split)

            # Combine snippet
            text_snippet = "\n".join(b.text for b in associated_blocks[:4])

            segment = CandidateSegment(
                page_index=page_index,
                bbox=seg_bbox,
                layout_element_ids=[idx for idx, _ in associated_elements],
                text_snippet=text_snippet,
            )

            candidate = LocalQuestionCandidate(
                question_number=m.number,
                segments=[segment],
                confidence=m.confidence,
                reasons=[f"Marker Q{m.number} at y={m.bbox[1]:.3f}"],
                has_options=has_options,
                options_found=options_found,
                question_type=q_type,
                needs_vlm=False,
            )
            candidates.append(candidate)

        return candidates

    def _find_next_stopping_marker(
        self,
        current: QuestionMarker,
        all_ordered: List[QuestionMarker],
    ) -> Optional[QuestionMarker]:
        """Find the next marker or section header following the current marker."""
        found = False
        for m in all_ordered:
            if m.number == current.number and m.bbox == current.bbox:
                found = True
                continue
            if found:
                return m
        return None

    def _same_column(self, m1: QuestionMarker, m2: QuestionMarker, is_two_col: bool, split: float) -> bool:
        if not is_two_col:
            return True
        col1 = (m1.bbox[0] + m1.bbox[2]) / 2 < split
        col2 = (m2.bbox[0] + m2.bbox[2]) / 2 < split
        return col1 == col2

    def _detect_options(self, blocks: List[OCRBlock]) -> List[str]:
        """Detect options A, B, C, D present in text blocks."""
        found: Set[str] = set()
        for b in blocks:
            for match in self.OPTION_REGEX.finditer(b.text):
                opt_letter = match.group(0).strip("()[]（）.,、 ")
                if opt_letter in ["A", "B", "C", "D"]:
                    found.add(opt_letter)
        return sorted(list(found))

    def _calculate_initial_bbox(
        self,
        marker: QuestionMarker,
        elements: List[Tuple[int, LayoutElement]],
        blocks: List[OCRBlock],
        is_two_col: bool,
        col: str,
        split: float,
    ) -> Tuple[float, float, float, float]:
        """Calculate initial bounding box covering marker and all associated elements."""
        x0, y0 = marker.bbox[0], marker.bbox[1]
        x1, y1 = marker.bbox[2], marker.bbox[3]

        # Expand with elements
        for _, elem in elements:
            x0 = min(x0, elem.bbox[0])
            y0 = min(y0, elem.bbox[1])
            x1 = max(x1, elem.bbox[2])
            y1 = max(y1, elem.bbox[3])

        # Expand with text blocks
        for blk in blocks:
            x0 = min(x0, blk.bbox[0])
            y0 = min(y0, blk.bbox[1])
            x1 = max(x1, blk.bbox[2])
            y1 = max(y1, blk.bbox[3])

        # Enforce column boundaries if two-column and item is confined to column
        if is_two_col and col != "full":
            if col == "left":
                x0 = max(0.02, min(x0, 0.04))
                x1 = min(split - 0.01, max(x1, 0.46))
            elif col == "right":
                x0 = max(split + 0.01, min(x0, split + 0.03))
                x1 = min(0.98, max(x1, 0.94))
        else:
            x0 = max(0.025, min(x0, 0.05))
            x1 = min(0.975, max(x1, 0.93))

        return (round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4))
