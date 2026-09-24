"""Multi-source question marker detector with robust false-positive suppression.

Detects Arabic and Chinese numeral question markers from text blocks,
filtering out dates (2020.), decimals (3.14), option letters (A, B, C, D),
isolated fractions, and section headers.
"""

import re
from typing import List, Optional, Tuple
from ..local_ai.types import OCRBlock, QuestionMarker


class LocalMarkerDetector:
    """Detects question number anchors from OCR and text blocks."""

    # Arabic numeral question marker regex: "1.", "17、", "22．", etc. (Must have punctuation, not just space)
    ARABIC_PATTERN = re.compile(r"^(?:第\s*)?(\d{1,2})[\.、．](?!\d)")
    
    # Chinese section header regex: "一、选择题", "二、填空题", "三、解答题"
    SECTION_PATTERN = re.compile(r"^([一二三四五六七八九十]+)[、\.\s]+(?:选择题|填空题|解答题|综合题|证明题|计算题)?")
    
    # Bracketed question marker: "（9）", "(15)"
    BRACKET_PATTERN = re.compile(r"^[（\(](\d{1,2})[）\)]")

    # Options to strictly avoid misidentifying as question markers
    OPTION_PREFIX_PATTERN = re.compile(r"^[\[\(（]?[A-Da-d][\)）\]\.\、\s]")

    def __init__(self) -> None:
        pass

    def detect_markers(
        self,
        text_blocks: List[OCRBlock],
        page_index: int,
    ) -> List[QuestionMarker]:
        """Extract and filter valid question markers from text blocks on a page."""
        raw_markers: List[QuestionMarker] = []

        for blk in text_blocks:
            text = blk.text.strip()
            if not text:
                continue

            # 1. Skip if text is an option line (A., B., C., D.)
            if self.OPTION_PREFIX_PATTERN.match(text):
                continue

            # 2. Skip if text contains option denominators with subsequent options, e.g. "4.\n(B)" or "3.\n(C)"
            if re.search(r"[\r\n]\s*[\(\[（]?[B-Db-d][\)\]）\.\、]", text):
                continue

            # 3. Skip if text looks like a date (e.g., "2020年", "2025.")
            if re.match(r"^(?:19|20)\d{2}[\.年]", text):
                continue

            # 4. Check section header (e.g. "一、选择题")
            sec_match = self.SECTION_PATTERN.match(text)
            if sec_match:
                raw_markers.append(
                    QuestionMarker(
                        number=sec_match.group(1),
                        page_index=page_index,
                        bbox=blk.bbox,
                        confidence=0.99,
                        source=blk.source,
                        raw_text=text[:30],
                        is_section_header=True,
                    )
                )
                continue

            # 5. Check Arabic numeral question marker (e.g. "1.", "17.")
            arabic_match = self.ARABIC_PATTERN.match(text)
            if arabic_match:
                # Filter out solitary numbers with punctuation and no stem words if indented (e.g. "4.", "3." from option fractions)
                if len(text) <= 3 and text.endswith((".", "、", "．")) and blk.bbox[0] > 0.165:
                    continue

                q_num_str = arabic_match.group(1)
                q_num = int(q_num_str)

                # Sanity range check (most Chinese exams have 1 ~ 35 questions)
                if 1 <= q_num <= 40:
                    # On page_index >= 2 (later pages of exam), numbers 1-4 are subquestions, not top-level questions
                    if 1 <= q_num <= 4 and page_index >= 2:
                        continue

                    # Filter out fraction denominator artifacts (e.g. isolated "4." on right side with short text)
                    if len(text) <= 4 and blk.bbox[0] > 0.60:
                        continue

                    # Filter out math lines that happen to have a decimal or formula continuation
                    after_match = text[arabic_match.end():].strip()
                    if after_match and after_match[0].isdigit():
                        continue

                    raw_markers.append(
                        QuestionMarker(
                            number=q_num_str,
                            page_index=page_index,
                            bbox=blk.bbox,
                            confidence=0.95,
                            source=blk.source,
                            raw_text=text[:30],
                            is_section_header=False,
                        )
                    )
                continue

            # 6. Check bracketed number (e.g. "(1)", "(9)", "(15)")
            bracket_match = self.BRACKET_PATTERN.match(text)
            if bracket_match:
                b_num_str = bracket_match.group(1)
                b_num = int(b_num_str)
                # If b_num >= 5, or if 1 <= b_num <= 4 on the first two pages (page_index <= 1) at the left margin
                if b_num >= 5 or (1 <= b_num <= 4 and page_index <= 1 and blk.bbox[0] < 0.22):
                    raw_markers.append(
                        QuestionMarker(
                            number=b_num_str,
                            page_index=page_index,
                            bbox=blk.bbox,
                            confidence=0.95,
                            source=blk.source,
                            raw_text=text[:30],
                            is_section_header=False,
                        )
                    )

        # Post-filter: Remove duplicate or out-of-sequence noisy markers
        return self._filter_and_deduplicate(raw_markers)

    def _filter_and_deduplicate(self, markers: List[QuestionMarker]) -> List[QuestionMarker]:
        """Deduplicate markers with same question number, preferring the higher confidence one."""
        deduped: dict[str, QuestionMarker] = {}
        for m in markers:
            if m.is_section_header:
                key = f"sec_{m.number}_{round(m.bbox[1], 2)}"
            else:
                key = f"q_{m.number}"

            if key not in deduped:
                deduped[key] = m
            else:
                # If already exists, keep the one higher up on the page or with higher confidence
                existing = deduped[key]
                if m.confidence > existing.confidence:
                    deduped[key] = m
                elif m.confidence == existing.confidence and m.bbox[1] < existing.bbox[1]:
                    deduped[key] = m

        # Return sorted by y-coordinate
        return sorted(deduped.values(), key=lambda m: (m.bbox[1], m.bbox[0]))
