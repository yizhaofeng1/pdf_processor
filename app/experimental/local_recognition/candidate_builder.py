"""Candidate Builder: Merging virtual regions, neighbor expansion, and overlap detection."""

from typing import List, Dict, Tuple, Optional
import pymupdf

from .types import CandidateRect, VirtualRegion, CoarseQuestionOutput
from .virtual_address import parse_virtual_address, format_virtual_address, get_neighbor_addresses
from .page_table import VirtualPageTable
from ...pdf.coordinate import calculate_overlap_ratio, clamp


class CandidateBuilder:
    """Constructs CandidateRects from coarse question outputs and virtual page tables."""

    def __init__(
        self,
        neighbor_radius: int = 1,
        padding_ratio: Tuple[float, float] = (0.015, 0.015),
        overlap_threshold: float = 0.4,
        full_width_layout: bool = False,
    ) -> None:
        self.neighbor_radius = neighbor_radius
        self.padding_ratio = padding_ratio
        self.overlap_threshold = overlap_threshold
        self.full_width_layout = full_width_layout

    def build_candidates_for_page(
        self,
        page_table: VirtualPageTable,
        coarse_questions: List[CoarseQuestionOutput],
    ) -> List[CandidateRect]:
        """Build candidate bounding rects for all questions detected on a single page."""
        candidates: List[CandidateRect] = []

        for q in coarse_questions:
            if not q.regions:
                continue

            # 1. Resolve and optionally expand regions
            region_addrs = set(q.regions)
            expanded = False

            if self.neighbor_radius > 0:
                expanded_addrs = set(region_addrs)
                for addr in list(region_addrs):
                    try:
                        neighbors = get_neighbor_addresses(
                            addr,
                            max_rows=page_table.rows,
                            max_cols=page_table.columns,
                            radius=self.neighbor_radius,
                        )
                        expanded_addrs.update(neighbors)
                    except Exception:
                        continue
                if len(expanded_addrs) > len(region_addrs):
                    expanded = True
                target_addrs = sorted(list(expanded_addrs))
            else:
                target_addrs = sorted(list(region_addrs))

            resolved_regions = page_table.resolve_multiple(target_addrs)
            if not resolved_regions:
                continue

            # 2. Compute minimal bounding box of all resolved regions
            min_x = min(r.normalized_rect[0] for r in resolved_regions)
            min_y = min(r.normalized_rect[1] for r in resolved_regions)
            max_x = max(r.normalized_rect[2] for r in resolved_regions)
            max_y = max(r.normalized_rect[3] for r in resolved_regions)

            # 3. Add safety padding and clamp
            pad_x = self.padding_ratio[0]
            pad_y = self.padding_ratio[1]

            if self.full_width_layout:
                # Single-column / full-width layout: extend to full horizontal width
                nx1 = 0.0
                nx2 = 1.0
            else:
                nx1 = clamp(min_x - pad_x, 0.0, 1.0)
                nx2 = clamp(max_x + pad_x, 0.0, 1.0)

            ny1 = clamp(min_y - pad_y, 0.0, 1.0)
            ny2 = clamp(max_y + pad_y, 0.0, 1.0)

            # 4. Map to PDF coordinates
            px0 = page_table.x0 + nx1 * page_table.width
            py0 = page_table.y0 + ny1 * page_table.height
            px1 = page_table.x0 + nx2 * page_table.width
            py1 = page_table.y0 + ny2 * page_table.height

            cand = CandidateRect(
                question_number=q.question_number,
                page_index=page_table.page_index,
                source_regions=sorted(list(region_addrs)),
                normalized_rect=(round(nx1, 6), round(ny1, 6), round(nx2, 6), round(ny2, 6)),
                pdf_rect=(round(px0, 2), round(py0, 2), round(px1, 2), round(py1, 2)),
                expanded=expanded,
                overlap_detected=False,
                verify_required=False,
            )
            candidates.append(cand)

        # 5. Prior-assisted sequential gap interpolation (e.g. Q3 between Q2 and Q4)
        candidates = self._interpolate_missing_sequential_questions(candidates, page_table)

        # 6. Overlap detection between different questions
        self._check_overlaps(candidates)

        return candidates

    def _interpolate_missing_sequential_questions(
        self,
        candidates: List[CandidateRect],
        page_table: VirtualPageTable,
    ) -> List[CandidateRect]:
        """Interpolate candidate bounding box for missing sequential questions on the same page."""
        numeric_items: List[Tuple[int, CandidateRect]] = []
        for c in candidates:
            digits = "".join(filter(str.isdigit, c.question_number))
            if digits:
                numeric_items.append((int(digits), c))

        if len(numeric_items) < 2:
            return candidates

        numeric_items.sort(key=lambda item: item[0])
        interpolated: List[CandidateRect] = list(candidates)

        for idx in range(len(numeric_items) - 1):
            n_curr, c_curr = numeric_items[idx]
            n_next, c_next = numeric_items[idx + 1]

            # If there's an exact gap of 1 question (e.g. detected 2 and 4, missing 3)
            if n_next - n_curr == 2:
                missing_num = str(n_curr + 1)
                # Compute vertical span centered between c_curr and c_next using average neighbor height
                mid_y = (c_curr.normalized_rect[1] + c_curr.normalized_rect[3] + c_next.normalized_rect[1] + c_next.normalized_rect[3]) / 4.0
                est_height = max(0.08, (c_curr.normalized_rect[3] - c_curr.normalized_rect[1] + c_next.normalized_rect[3] - c_next.normalized_rect[1]) / 2.0)
                gap_y1 = max(0.0, mid_y - est_height / 2.0)
                gap_y2 = min(1.0, mid_y + est_height / 2.0)

                if gap_y2 > gap_y1:
                    nx1 = 0.0 if self.full_width_layout else c_curr.normalized_rect[0]
                    nx2 = 1.0 if self.full_width_layout else c_curr.normalized_rect[2]

                    px0 = page_table.x0 + nx1 * page_table.width
                    py0 = page_table.y0 + gap_y1 * page_table.height
                    px1 = page_table.x0 + nx2 * page_table.width
                    py1 = page_table.y0 + gap_y2 * page_table.height

                    inter_cand = CandidateRect(
                        question_number=missing_num,
                        page_index=page_table.page_index,
                        source_regions=[f"P{page_table.page_index:02d}:INTERPOLATED"],
                        normalized_rect=(round(nx1, 6), round(gap_y1, 6), round(nx2, 6), round(gap_y2, 6)),
                        pdf_rect=(round(px0, 2), round(py0, 2), round(px1, 2), round(py1, 2)),
                        expanded=True,
                        overlap_detected=False,
                        verify_required=False,
                    )
                    interpolated.append(inter_cand)

        # Re-sort candidates numerically
        def _sort_key(c: CandidateRect) -> int:
            digits = "".join(filter(str.isdigit, c.question_number))
            return int(digits) if digits else 9999

        interpolated.sort(key=_sort_key)
        return interpolated

    def _check_overlaps(self, candidates: List[CandidateRect]) -> None:
        """Check for excessive overlaps between candidates on the same page."""
        n = len(candidates)
        for i in range(n):
            for j in range(i + 1, n):
                c1 = candidates[i]
                c2 = candidates[j]
                overlap = calculate_overlap_ratio(c1.normalized_rect, c2.normalized_rect)
                if overlap >= self.overlap_threshold:
                    c1.overlap_detected = True
                    c2.overlap_detected = True
                    c1.verify_required = True
                    c2.verify_required = True
