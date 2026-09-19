"""Cross-Page Resolver: Identifies and merges questions spanning across page boundaries.

Per Design Doc Section 10:
A single Question model holds multiple QuestionSegment objects.
Cross-page questions MUST NOT be duplicated into separate Question models.
"""

from typing import List, Dict
import logging

from ..models.question import Question, QuestionType
from ..models.segment import QuestionSegment
from ..models.question import AnchorPoint

logger = logging.getLogger("examsplit.detection.cross_page")


class CrossPageResolver:
    """Detects and reconciles multi-page question continuations across adjacent pages."""

    def __init__(
        self,
        bottom_threshold: float = 0.85,
        top_continuation_margin: float = 0.04,
    ) -> None:
        self.bottom_threshold = bottom_threshold
        self.top_continuation_margin = top_continuation_margin

    def resolve(
        self,
        page_questions_map: Dict[int, List[Question]],
        page_count: int,
    ) -> List[Question]:
        """Reconcile questions across consecutive pages and return a flattened, sorted list of Questions."""
        all_questions: List[Question] = []

        for p_idx in range(page_count):
            curr_page_qs = page_questions_map.get(p_idx, [])
            if not curr_page_qs:
                continue

            # Check if this page's first question continuation needs to be absorbed by previous page's last question
            # However, if it's already structured by AI (segments contain multiple pages), it's handled.
            all_questions.extend(curr_page_qs)

        # Now perform adjacent page continuation analysis
        # Group by page
        pages: List[int] = sorted(page_questions_map.keys())

        for i in range(len(pages) - 1):
            p_curr = pages[i]
            p_next = pages[i + 1]

            # Only check immediately adjacent pages (p_next == p_curr + 1)
            if p_next != p_curr + 1:
                continue

            curr_qs = page_questions_map.get(p_curr, [])
            next_qs = page_questions_map.get(p_next, [])

            if not curr_qs:
                continue

            last_q = curr_qs[-1]

            # If last_q already spans across multiple pages, skip
            pages_in_last_q = {s.page_index for s in last_q.segments}
            if p_next in pages_in_last_q:
                continue

            # Check if last question's bottom is close to the bottom of p_curr
            last_seg = last_q.segments[-1] if last_q.segments else None
            if not last_seg:
                continue

            is_near_bottom = last_seg.normalized_bbox[3] >= self.bottom_threshold

            # Case A: next page has NO questions at all (the entire next page is continuation)
            if not next_qs and is_near_bottom:
                cont_seg = QuestionSegment(
                    question_id=last_q.id,
                    page_index=p_next,
                    normalized_bbox=(
                        last_seg.normalized_bbox[0],
                        self.top_continuation_margin,
                        last_seg.normalized_bbox[2],
                        0.95,
                    ),
                )
                last_q.segments.append(cont_seg)
                last_q.continuation = True
                logger.info(f"Question {last_q.display_number} spans entirely across Page {p_curr} to {p_next}")
                continue

            # Case B: next page starts with a gap before the first question
            if next_qs and is_near_bottom:
                first_next_q = next_qs[0]
                first_next_seg = first_next_q.segments[0] if first_next_q.segments else None

                if first_next_seg:
                    first_y_top = first_next_seg.normalized_bbox[1]
                    # If first question on next page starts significantly down the page (gap >= 0.15)
                    # and the question numbers are sequential (e.g. last_q=17, first_next_q=18)
                    is_sequential = False
                    try:
                        curr_num = int(last_q.display_number)
                        next_num = int(first_next_q.display_number)
                        is_sequential = (next_num == curr_num + 1)
                    except ValueError:
                        is_sequential = True  # Can't parse integers, allow heuristic

                    if first_y_top >= 0.18 and is_sequential:
                        # The region from page top to first_y_top is the continuation of last_q!
                        cont_seg = QuestionSegment(
                            question_id=last_q.id,
                            page_index=p_next,
                            normalized_bbox=(
                                last_seg.normalized_bbox[0],
                                self.top_continuation_margin,
                                last_seg.normalized_bbox[2],
                                max(self.top_continuation_margin + 0.05, first_y_top - 0.01),
                            ),
                        )
                        last_q.segments.append(cont_seg)
                        last_q.continuation = True
                        logger.info(
                            f"Merged cross-page continuation for Question {last_q.display_number} "
                            f"(Page {p_curr} -> Page {p_next} [y: {self.top_continuation_margin:.2f} ~ {first_y_top:.2f}])"
                        )

        # Re-sort all questions by first segment (page_index, y1)
        all_questions.sort(
            key=lambda q: (
                q.segments[0].page_index if q.segments else 0,
                q.segments[0].normalized_bbox[1] if q.segments else 0.0,
            )
        )

        for sort_idx, q in enumerate(all_questions):
            q.sort_order = sort_idx

        return all_questions
