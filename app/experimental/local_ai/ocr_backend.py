"""Text extraction and OCR backends for document pages.

Prioritizes native digital text (zero OCR hallucination, perfect coordinates)
with fallback to local OCR when pages are scanned or contain image-only text.
"""

import logging
from typing import Any, List, Optional
from .base import LocalOCRProvider
from .config import LocalModelConfig
from .types import OCRBlock

logger = logging.getLogger("examsplit.experimental.local_ai.ocr")


class HybridOCRProvider(LocalOCRProvider):
    """Hybrid provider: Native vector text first, OCR fallback for scanned pages."""

    def __init__(self) -> None:
        self._paddle_ocr = None
        self._ocr_checked = False

    def is_available(self) -> bool:
        return True

    def _ensure_ocr_engine(self) -> Any:
        if not self._ocr_checked:
            self._ocr_checked = True
            try:
                from paddleocr import PaddleOCR  # type: ignore
                self._paddle_ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
                logger.info("PaddleOCR engine loaded for hybrid fallback.")
            except Exception as e:
                logger.debug(f"PaddleOCR not available for fallback: {e}")
                self._paddle_ocr = None
        return self._paddle_ocr

    def extract_text_blocks(
        self,
        page_image_path: Optional[str],
        page_index: int,
        pdf_page: Any = None,
    ) -> List[OCRBlock]:
        blocks: List[OCRBlock] = []

        # 1. Native PyMuPDF text extraction
        if pdf_page is not None:
            page_rect = pdf_page.rect
            p_w, p_h = page_rect.width, page_rect.height
            if p_w > 0 and p_h > 0:
                raw_dict = pdf_page.get_text("dict")
                for blk in raw_dict.get("blocks", []):
                    if blk.get("type") == 0:  # text block
                        # We can extract at line level for fine granularity
                        for line in blk.get("lines", []):
                            line_text = "".join(span.get("text", "") for span in line.get("spans", "")).strip()
                            if not line_text:
                                continue
                            lx0, ly0, lx1, ly1 = line.get("bbox", (0, 0, 0, 0))
                            blocks.append(
                                OCRBlock(
                                    text=line_text,
                                    bbox=(lx0 / p_w, ly0 / p_h, lx1 / p_w, ly1 / p_h),
                                    confidence=1.0,
                                    page_index=page_index,
                                    source="native_pdf",
                                )
                            )

        # 2. Check if native extraction yielded sufficient content
        total_chars = sum(len(b.text) for b in blocks)
        if total_chars >= 30:
            # High-confidence native digital text
            return blocks

        # 3. Fallback to OCR if page has sparse text (e.g. scanned exam paper)
        if page_image_path:
            ocr_engine = self._ensure_ocr_engine()
            if ocr_engine is not None:
                try:
                    import cv2  # type: ignore
                    img = cv2.imread(page_image_path)
                    if img is not None:
                        h, w = img.shape[:2]
                        ocr_res = ocr_engine.ocr(img, cls=True)
                        if ocr_res and len(ocr_res) > 0 and ocr_res[0]:
                            ocr_blocks: List[OCRBlock] = []
                            for line in ocr_res[0]:
                                poly = line[0]
                                text_info = line[1]
                                txt = text_info[0].strip()
                                score = float(text_info[1])
                                xs = [pt[0] for pt in poly]
                                ys = [pt[1] for pt in poly]
                                x0, x1 = min(xs) / w, max(xs) / w
                                y0, y1 = min(ys) / h, max(ys) / h
                                ocr_blocks.append(
                                    OCRBlock(
                                        text=txt,
                                        bbox=(x0, y0, x1, y1),
                                        confidence=score,
                                        page_index=page_index,
                                        source="ocr",
                                    )
                                )
                            if ocr_blocks:
                                return ocr_blocks
                except Exception as e:
                    logger.warning(f"Fallback OCR processing failed: {e}")

        return blocks


def get_ocr_provider(config: LocalModelConfig) -> LocalOCRProvider:
    """Factory creating the OCR provider."""
    return HybridOCRProvider()
