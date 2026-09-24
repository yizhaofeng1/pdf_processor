"""Confidence scoring and routing engine for candidates.

Decides whether a candidate can be accepted directly via deterministic rules (high confidence)
or requires review by the local vision-language model (low confidence or anomalies).
"""

from typing import List
from ..local_ai.config import LocalModelConfig
from ..local_ai.types import LocalQuestionCandidate


class LocalConfidenceRouter:
    """Evaluates candidate confidence and flags items for VLM verification."""

    def __init__(self, config: LocalModelConfig) -> None:
        self.config = config

    def evaluate_and_route(
        self,
        candidates: List[LocalQuestionCandidate],
    ) -> List[LocalQuestionCandidate]:
        """Evaluate confidence for candidates and set needs_vlm flag."""
        if not candidates:
            return []

        # Sort by numerical order if possible
        sorted_cand = sorted(
            candidates,
            key=lambda c: int(c.question_number) if c.question_number.isdigit() else 999,
        )

        for i, c in enumerate(sorted_cand):
            score = c.confidence

            # 1. Check sequential continuity
            if i > 0 and sorted_cand[i - 1].question_number.isdigit() and c.question_number.isdigit():
                prev_n = int(sorted_cand[i - 1].question_number)
                curr_n = int(c.question_number)
                if curr_n == prev_n + 1:
                    score = min(1.0, score + 0.05)
                elif curr_n > prev_n + 1:
                    # Missing intermediate question marker
                    score -= 0.15
                    c.reasons.append(f"Sequence gap: Q{prev_n} to Q{curr_n}")

            # 2. Check multiple-choice option completeness
            if c.question_type == "choice":
                if c.has_options:
                    score = min(1.0, score + 0.05)
                else:
                    score -= 0.20
                    c.reasons.append(f"Incomplete options: only found {c.options_found}")

            # 3. Check bounding box dimensions
            if c.segments:
                seg = c.segments[0]
                h = seg.bbox[3] - seg.bbox[1]
                w = seg.bbox[2] - seg.bbox[0]
                if h < 0.025:
                    score -= 0.25
                    c.reasons.append("Abnormally small vertical height")
                elif h > 0.90:
                    score -= 0.10
                    c.reasons.append("Very tall bounding box")

                # Check proximity to bottom of page (potential cross-page)
                if seg.bbox[3] > 0.91 and c.question_type == "solution":
                    score -= 0.10
                    c.reasons.append("Near page bottom: check cross-page continuation")

            c.confidence = max(0.10, min(1.0, round(score, 3)))

            # Route to VLM if below threshold and not in fast mode
            if self.config.mode == "fast":
                c.needs_vlm = False
            else:
                c.needs_vlm = c.confidence < self.config.confidence_threshold

        return candidates
