"""Marker Detector for Question Identification.

Detects question start markers (e.g. '1.', '17．', '一、选择题') on PDF pages
using native PDF text analysis and/or Vision-Language AI providers.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
import re
import logging
from pathlib import Path

from ..models.question import QuestionType, AnchorPoint
from ..models.segment import QuestionSegment
from ..models.ai_result import VisionAnalysisRequest, VisionAnalysisResult
from ..pdf.reader import PDFReader, PageType
from ..pdf.renderer import PDFRenderer
from ..pdf.coordinate import pdf_rect_to_normalized

logger = logging.getLogger("examsplit.detection.marker")


@dataclass
class QuestionMarker:
    """Represents a localized question marker/anchor on a page."""
    number: str
    page_index: int
    normalized_point: Tuple[float, float]  # (x, y) normalized [0.0, 1.0]
    normalized_bbox: Optional[Tuple[float, float, float, float]] = None
    question_type: Optional[QuestionType | str] = None
    confidence: float = 1.0
    raw_text: str = ""
    is_section_header: bool = False


# Regex patterns for Chinese exam question numbers
# Matches "(1)", "（1）", "【1】", "1.", "1．", "1、", "第1题", "17.", "Q1"
QUESTION_NUM_PATTERN = re.compile(
    r"^(?:[\(（【\[]\s*([0-9]{1,2})\s*[\)）】\]]|(?:第\s*)?(\d{1,2})\s*[．\.\、\)）]|(?:Q|q)(\d{1,2})[\.:\s]?|(?:第\s*)(\d{1,2})\s*(?:小?题))"
)

# Major section headers e.g. "一、选择题", "二、填空题", "三、解答题"
SECTION_HEADER_PATTERN = re.compile(
    r"^([一二三四五六七八九十]+)\s*[、\.]\s*(选择题|填空题|解答题|证明题|综合题|计算题)"
)

ROMAN_NUM_MAP = {
    "I": "1", "i": "1", "l": "1",
    "II": "2", "ii": "2",
    "III": "3", "iii": "3",
    "IV": "4", "iv": "4",
    "V": "5", "v": "5",
    "VI": "6", "vi": "6",
    "VII": "7", "vii": "7",
    "VIII": "8", "viii": "8",
    "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
    "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
}


class NativeTextMarkerDetector:
    """Extracts question markers using PyMuPDF native text and word bounding boxes."""

    def __init__(self, reader: PDFReader) -> None:
        self.reader = reader

    def detect_page(self, page_index: int) -> List[QuestionMarker]:
        """Detect question markers on a specific page using text extraction."""
        page_info = self.reader.get_page_info(page_index)
        if page_info.page_type == PageType.IMAGE_PDF:
            # Scanned page has no native text blocks
            return []

        if not (0 <= page_index < self.reader.page_count):
            return []

        page = self.reader.get_page(page_index)
        page_w = page.rect.width
        page_h = page.rect.height
        if page_w <= 0 or page_h <= 0:
            return []

        # Extract text blocks: (x0, y0, x1, y1, text, block_no, block_type)
        blocks = page.get_text("blocks")
        markers: List[QuestionMarker] = []
        current_section_type: Optional[QuestionType] = None

        for block in blocks:
            if len(block) < 5 or block[6] != 0:  # block_type 0 is text
                continue

            bx0, by0, bx1, by1, text = block[0], block[1], block[2], block[3], block[4]
            lines = [line.strip() for line in text.splitlines() if line.strip()]

            for line_idx, line in enumerate(lines):
                # 1. Check if section header
                sec_match = SECTION_HEADER_PATTERN.match(line)
                if sec_match:
                    sec_name = sec_match.group(2)
                    if "选择" in sec_name or "填空" in sec_name:
                        current_section_type = QuestionType.SMALL
                    elif "解答" in sec_name or "计算" in sec_name or "证明" in sec_name:
                        current_section_type = QuestionType.LARGE
                    continue

                # 2. Check if question number
                q_match = QUESTION_NUM_PATTERN.match(line)
                if q_match:
                    raw_num = q_match.group(1) or q_match.group(2) or q_match.group(3) or q_match.group(4)
                    num_str = str(int(raw_num))
                elif current_section_type == QuestionType.SMALL and re.match(r"^[\(（【\[]\s*(?:I|i|l)\s*[\)）】\]]", line) and not any(m.number == "1" for m in markers):
                    raw_num = "1"
                    num_str = "1"
                else:
                    continue

                # Approximate vertical position within block if multiple lines
                line_ratio = line_idx / max(len(lines), 1)
                ly0 = by0 + (by1 - by0) * line_ratio

                nx = max(0.0, min(1.0, bx0 / page_w))
                ny = max(0.0, min(1.0, ly0 / page_h))

                # Filter Rule 1: No valid exam question starts in the far-right margin (> 0.68)
                if nx > 0.68:
                    continue

                # Filter Rule 2: Standalone digit without Chinese text in block, or block contains options (A)/(B)/(C)/(D)
                # (e.g. choice fraction denominators '4.', '3.', '2.', '12.')
                is_solitary_num = bool(re.match(r"^\d{1,2}[．\.\、]?$", line))
                if is_solitary_num:
                    has_chinese = bool(re.search(r"[\u4e00-\u9fa5]", text))
                    has_options = bool(re.search(r"[\(（\[]?[A-D][\)）\]\.]", text))
                    if has_options or not has_chinese:
                        continue

                # Filter Rule 3: Sub-question suppression: bracketed small numbers (1)/(2)/(3)/(4)
                # when inside a LARGE (解答题) section or after Page 0
                is_bracketed_small_num = bool(re.match(r"^[\(（【\[]\s*([1-9])\s*[\)）】\]]", line))
                if is_bracketed_small_num and int(num_str) <= 4:
                    if current_section_type == QuestionType.LARGE or (page_index > 0 and any(m.number not in ('1', '2', '3', '4') for m in markers)):
                        continue

                # Infer question type based on section or typical Chinese math exam conventions
                q_type = current_section_type
                if not q_type:
                    try:
                        n = int(num_str)
                        if 1 <= n <= 14:
                            q_type = QuestionType.SMALL
                        elif n >= 15:
                            q_type = QuestionType.LARGE
                    except ValueError:
                        pass

                marker = QuestionMarker(
                    number=num_str,
                    page_index=page_index,
                    normalized_point=(nx, ny),
                    question_type=q_type,
                    confidence=0.95,
                    raw_text=line[:60],
                )
                markers.append(marker)

        # Deduplicate same-number candidates on the same page (e.g. prefer line with actual question text)
        if len(markers) > 1:
            from collections import defaultdict
            grouped = defaultdict(list)
            for m in markers:
                grouped[m.number].append(m)
            
            deduped: List[QuestionMarker] = []
            for num_key, items in grouped.items():
                if len(items) == 1:
                    deduped.append(items[0])
                else:
                    # Prefer item with Chinese characters in raw_text
                    with_cn = [it for it in items if re.search(r"[\u4e00-\u9fa5]", it.raw_text)]
                    deduped.append(with_cn[0] if with_cn else items[0])
            markers = deduped

        # Sort markers by vertical reading order (top-to-bottom)
        markers.sort(key=lambda m: m.normalized_point[1])
        return markers



class AIMarkerDetector:
    """Detects question markers and regions using a VisionModelProvider."""

    def __init__(self, provider, cache_dir: Optional[Path] = None) -> None:
        self.provider = provider
        self.cache_dir = cache_dir or Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def detect_page(
        self,
        reader: PDFReader,
        page_index: int,
        context_hints: Optional[dict] = None,
    ) -> List[QuestionMarker]:
        """Render page, call AI provider, and extract question markers."""
        # 1. Render page image to cache
        img_path = self.cache_dir / f"page_{page_index}_{reader.file_hash[:8]}.png"
        if not img_path.exists():
            PDFRenderer.render_page_to_image_file(reader, page_index, img_path, dpi=180)

        # 2. Build analysis request
        req = VisionAnalysisRequest(
            page_indices=[page_index],
            image_paths=[str(img_path)],
            pdf_path=str(reader.file_path),
            context_hints=context_hints or {},
        )

        # 3. Call AI provider with 1 retry on timeout/network error
        last_exc = None
        result = None
        for attempt in range(2):
            try:
                result = self.provider.analyze_pages(req)
                break
            except Exception as e:
                last_exc = e
                err_str = str(e).lower()
                if attempt == 0 and any(k in err_str for k in ("timeout", "timed out", "connection", "remote protocol")):
                    logger.info(f"Page {page_index}: AI vision call transient error ({e}), retrying once...")
                    continue
                logger.warning(f"AI Vision call failed for page {page_index} ({e}).")
                raise e


        # 4. Map questions to markers
        markers: List[QuestionMarker] = []
        for q in result.questions:
            # Determine anchor point from first segment or start_anchor
            if q.segments:
                seg = q.segments[0]
                pt = (seg.normalized_bbox[0], seg.normalized_bbox[1])
                bbox = seg.normalized_bbox
            elif q.start_anchor:
                pt = q.start_anchor.normalized_point
                bbox = None
            else:
                pt = (0.05, 0.1)
                bbox = None

            marker = QuestionMarker(
                number=q.display_number,
                page_index=page_index,
                normalized_point=pt,
                normalized_bbox=bbox,
                question_type=q.question_type,
                confidence=q.confidence,
                raw_text="",
            )
            markers.append(marker)

        markers.sort(key=lambda m: m.normalized_point[1])
        return markers

    def generate_fallback_markers(self, page_index: int, error_msg: str = "") -> List[QuestionMarker]:
        """Generate candidate region markers when AI service is unavailable."""
        fallback_slots = [
            (f"P{page_index + 1}-1", (0.05, 0.08)),
            (f"P{page_index + 1}-2", (0.05, 0.50)),
        ]
        return [
            QuestionMarker(
                number=num,
                page_index=page_index,
                normalized_point=pt,
                confidence=0.40,
                raw_text=f"备用切分 (AI未返回: {error_msg[:40]})" if error_msg else "备用切分",
            )
            for num, pt in fallback_slots
        ]


class HybridMarkerDetector:
    """Combines AI vision detection and native text analysis with graceful fallback."""

    def __init__(self, reader: PDFReader, ai_detector: Optional[AIMarkerDetector] = None) -> None:
        self.reader = reader
        self.native_detector = NativeTextMarkerDetector(reader)
        self.ai_detector = ai_detector

    def detect_page(self, page_index: int, context_hints: Optional[dict[str, str]] = None) -> List[QuestionMarker]:
        """Detect markers: prioritize AI vision if configured; fallback to native text detector."""
        # 1. Prioritize AI vision detector if configured (Vision-first architecture)
        if self.ai_detector:
            try:
                ai_markers = self.ai_detector.detect_page(self.reader, page_index, context_hints=context_hints)
                if ai_markers and len(ai_markers) > 0:
                    logger.info(f"Page {page_index}: AI vision detector successfully identified {len(ai_markers)} markers.")
                    return ai_markers

                else:
                    logger.warning(f"Page {page_index}: AI vision returned 0 markers, falling back to native text detector.")
            except Exception as e:
                logger.warning(f"Page {page_index}: AI vision detector failed ({e}), falling back to native text detector.")

        # 2. Native text detector fallback
        page_info = self.reader.get_page_info(page_index)
        if page_info.page_type != PageType.IMAGE_PDF:
            native_markers = self.native_detector.detect_page(page_index)
            if native_markers and len(native_markers) > 0:
                logger.info(f"Page {page_index}: Found {len(native_markers)} markers via native text detector.")
                return native_markers

        # 3. Last-resort fallback slots
        logger.warning(f"Page {page_index}: Neither AI nor native text detected markers, generating fallback slots.")
        if self.ai_detector:
            return self.ai_detector.generate_fallback_markers(page_index)
        fallback_detector = AIMarkerDetector(None)
        return fallback_detector.generate_fallback_markers(page_index)
