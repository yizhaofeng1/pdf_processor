"""Cross-page question continuity resolver.

Detects when a question starts near the bottom of page K and continues onto
the top of page K+1 before the first question marker on that page.
"""

from typing import Dict, List
from ..local_ai.types import (
    CandidateSegment,
    LocalPageAnalysis,
    LocalQuestionCandidate,
)


class LocalCrossPageResolver:
    """Analyzes and merges cross-page question continuations across adjacent pages."""

    def resolve_cross_page_candidates(
        self,
        candidates_by_page: Dict[int, List[LocalQuestionCandidate]],
        page_analyses: Dict[int, LocalPageAnalysis],
    ) -> List[LocalQuestionCandidate]:
        """Merge cross-page question segments across consecutive pages."""
        sorted_pages = sorted(candidates_by_page.keys())
        all_candidates: List[LocalQuestionCandidate] = []

        for p_idx in range(len(sorted_pages)):
            curr_p = sorted_pages[p_idx]
            curr_candidates = candidates_by_page[curr_p]

            # Check if there is a next page
            if p_idx + 1 < len(sorted_pages):
                next_p = sorted_pages[p_idx + 1]
                next_analysis = page_analyses.get(next_p)
                next_candidates = candidates_by_page.get(next_p, [])

                if curr_candidates and next_analysis:
                    last_cand = curr_candidates[-1]
                    if last_cand.segments:
                        last_seg = last_cand.segments[-1]
                        # If ends near bottom
                        if last_seg.bbox[3] > 0.88:
                            # Check if next page has leading content before first marker
                            first_marker_y = 0.95
                            if next_candidates and next_candidates[0].segments:
                                first_marker_y = next_candidates[0].segments[0].bbox[1]

                            # Leading text blocks on next page
                            leading_blocks = [
                                b for b in next_analysis.text_blocks
                                if b.bbox[1] > 0.08 and b.bbox[3] < first_marker_y - 0.01
                            ]

                            if leading_blocks:
                                x0 = min(b.bbox[0] for b in leading_blocks)
                                y0 = min(b.bbox[1] for b in leading_blocks)
                                x1 = max(b.bbox[2] for b in leading_blocks)
                                y1 = max(b.bbox[3] for b in leading_blocks)

                                # Create continuation segment on next page
                                continuation_seg = CandidateSegment(
                                    page_index=next_p,
                                    bbox=(round(max(0.04, x0 - 0.015), 4),
                                          round(max(0.08, y0 - 0.01), 4),
                                          round(min(0.96, x1 + 0.015), 4),
                                          round(min(first_marker_y - 0.005, y1 + 0.01), 4)),
                                    text_snippet="\n".join(b.text for b in leading_blocks[:2]),
                                )
                                last_cand.segments.append(continuation_seg)
                                last_cand.reasons.append(f"Extended cross-page to page {next_p + 1}")

            all_candidates.extend(curr_candidates)

        return all_candidates
