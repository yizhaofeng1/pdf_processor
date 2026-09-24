"""Layout analysis backends for document parsing.

Provides:
- PaddleOCRLayoutProvider: Uses PP-DocLayoutV3 (via paddleocr/PPStructure) when installed.
- NativeDocLayoutProvider: High-fidelity PyMuPDF vector extraction fallback, classifying
  text, formulas, images, drawings, section titles, headers, and footers without requiring
  heavy external deep learning frameworks.
- get_layout_provider: Factory routing to the best available backend.
"""

import logging
import re
from typing import Any, List, Optional, Tuple
from .base import LocalLayoutProvider
from .config import LocalModelConfig
from .exceptions import LayoutModelError
from .types import LayoutElement

logger = logging.getLogger("examsplit.experimental.local_ai.layout")


class PaddleOCRLayoutProvider(LocalLayoutProvider):
    """Layout analysis provider using PP-DocLayoutV3 via PaddleOCR."""

    def __init__(self) -> None:
        self._engine = None
        self._available = False
        try:
            from paddleocr import PPStructure  # type: ignore
            self._engine = PPStructure(table=False, ocr=False, show_log=False)
            self._available = True
            logger.info("PP-DocLayoutV3 provider initialized successfully.")
        except Exception as e:
            logger.debug(f"PaddleOCR layout engine not available: {e}")
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def analyze_page(
        self,
        page_image_path: Optional[str],
        page_index: int,
        pdf_page: Any = None,
    ) -> List[LayoutElement]:
        if not self._available or not page_image_path:
            raise LayoutModelError("PaddleOCR layout engine is not available or image path is missing.")

        try:
            import cv2  # type: ignore
            img = cv2.imread(page_image_path)
            if img is None:
                raise LayoutModelError(f"Failed to read image at {page_image_path}")
            h, w = img.shape[:2]

            result = self._engine(img)
            elements: List[LayoutElement] = []
            category_mapping = {
                "text": "text",
                "title": "title",
                "figure": "image",
                "figure_caption": "text",
                "table": "table",
                "table_caption": "text",
                "header": "header",
                "footer": "footer",
                "reference": "text",
                "equation": "formula",
            }

            for idx, res in enumerate(result):
                bbox_px = res.get("bbox", [0, 0, 0, 0])
                raw_type = res.get("type", "text").lower()
                category = category_mapping.get(raw_type, "text")

                # Normalize coordinates (x1, y1, x2, y2)
                x1 = bbox_px[0] / max(w, 1)
                y1 = bbox_px[1] / max(h, 1)
                x2 = bbox_px[2] / max(w, 1)
                y2 = bbox_px[3] / max(h, 1)

                elements.append(
                    LayoutElement(
                        page_index=page_index,
                        category=category,
                        bbox=(x1, y1, x2, y2),
                        confidence=float(res.get("score", 0.9)),
                        order_hint=idx,
                    )
                )

            return elements
        except Exception as e:
            logger.error(f"Error in PaddleOCRLayoutProvider: {e}")
            raise LayoutModelError(f"PP-DocLayoutV3 execution failed: {e}") from e


class NativeDocLayoutProvider(LocalLayoutProvider):
    """High-fidelity vector layout analyzer using PyMuPDF native page structures.

    Extracts text blocks, section titles, headers, footers, math formulas,
    raster images, and vector diagrams with zero extra ML dependencies.
    """

    def is_available(self) -> bool:
        return True

    def analyze_page(
        self,
        page_image_path: Optional[str],
        page_index: int,
        pdf_page: Any = None,
    ) -> List[LayoutElement]:
        if pdf_page is None:
            # Cannot perform native layout without PyMuPDF page object
            return []

        elements: List[LayoutElement] = []
        page_rect = pdf_page.rect
        p_w, p_h = page_rect.width, page_rect.height
        if p_w <= 0 or p_h <= 0:
            return []

        # 1. Native text blocks and titles
        text_blocks = pdf_page.get_text("blocks")
        for idx, blk in enumerate(text_blocks):
            # blk: (x0, y0, x1, y1, text, block_no, block_type)
            # block_type == 0: text, 1: image
            x0, y0, x1, y1, text, block_no, blk_type = blk[:7]
            if blk_type == 1:
                # Embedded raster image block
                elements.append(
                    LayoutElement(
                        page_index=page_index,
                        category="image",
                        bbox=(x0 / p_w, y0 / p_h, x1 / p_w, y1 / p_h),
                        confidence=0.98,
                        order_hint=idx,
                    )
                )
                continue

            cleaned_text = text.strip()
            if not cleaned_text:
                continue

            ny0, ny1 = y0 / p_h, y1 / p_h
            category = "text"

            # Check header
            if ny1 <= 0.08 and any(h_kw in cleaned_text for h_kw in ["绝密", "试卷", "全国", "考研", "考试", "科目"]):
                category = "header"
            # Check footer
            elif ny0 >= 0.93 and any(f_kw in cleaned_text for f_kw in ["页", "第", "共", "—", "-"]):
                category = "footer"
            # Check Section Title (e.g. "一、选择题", "二、填空题", "三、解答题")
            elif re.match(r"^[一二三四五六七八九十]+[、\.\s]+", cleaned_text):
                category = "title"
            # Check formula (presence of math operators, integral, summation, matrices)
            elif any(sym in cleaned_text for sym in ["∫", "∑", "lim", "∂", "±", "×", "÷", "≤", "≥", "≠", "∞", "∈", "dx", "dy"]):
                if len(cleaned_text) < 40 and not re.match(r"^\d+[\.\、]", cleaned_text):
                    category = "formula"

            elements.append(
                LayoutElement(
                    page_index=page_index,
                    category=category,
                    bbox=(x0 / p_w, y0 / p_h, x1 / p_w, y1 / p_h),
                    confidence=0.95,
                    order_hint=idx,
                    text=cleaned_text,
                )
            )

        # 2. Vector drawings / geometric figures (diagrams)
        try:
            drawings = pdf_page.get_drawings()
            drawing_rects = []
            for d in drawings:
                r = d.get("rect")
                if r and r.width > 20 and r.height > 20:
                    drawing_rects.append(r)

            # Cluster overlapping/adjacent drawings into unified figure elements
            merged_figures = self._cluster_drawing_rects(drawing_rects, p_w, p_h)
            for fig_idx, fig_box in enumerate(merged_figures):
                elements.append(
                    LayoutElement(
                        page_index=page_index,
                        category="figure",
                        bbox=fig_box,
                        confidence=0.90,
                        order_hint=1000 + fig_idx,
                    )
                )
        except Exception as e:
            logger.debug(f"Drawings extraction note: {e}")

        # 3. Embedded images from get_images
        try:
            img_list = pdf_page.get_images()
            for img_info in img_list:
                xref = img_info[0]
                img_rects = pdf_page.get_image_rects(xref)
                for r in img_rects:
                    if r.width > 15 and r.height > 15:
                        elements.append(
                            LayoutElement(
                                page_index=page_index,
                                category="image",
                                bbox=(r.x0 / p_w, r.y0 / p_h, r.x1 / p_w, r.y1 / p_h),
                                confidence=0.99,
                                order_hint=2000,
                            )
                        )
        except Exception as e:
            logger.debug(f"Image rects extraction note: {e}")

        return elements

    def _cluster_drawing_rects(
        self,
        rects: List[Any],
        p_w: float,
        p_h: float,
    ) -> List[Tuple[float, float, float, float]]:
        """Cluster adjacent drawing rectangles into cohesive figure bounding boxes."""
        if not rects:
            return []

        clusters: List[Any] = []
        for r in rects:
            matched = False
            for c in clusters:
                # If distance between rects is small, merge
                if abs(r.x0 - c.x1) < 15 or abs(c.x0 - r.x1) < 15 or r.intersects(c):
                    if abs(r.y0 - c.y1) < 25 or abs(c.y0 - r.y1) < 25 or r.intersects(c):
                        c |= r
                        matched = True
                        break
            if not matched:
                clusters.append(r)

        result: List[Tuple[float, float, float, float]] = []
        for c in clusters:
            if c.width > 30 and c.height > 30:
                result.append((
                    max(0.0, c.x0 / p_w),
                    max(0.0, c.y0 / p_h),
                    min(1.0, c.x1 / p_w),
                    min(1.0, c.y1 / p_h),
                ))
        return result


def get_layout_provider(config: LocalModelConfig) -> LocalLayoutProvider:
    """Factory creating the appropriate layout provider according to config."""
    if config.layout_backend == "paddle":
        provider = PaddleOCRLayoutProvider()
        if provider.is_available():
            return provider
        logger.warning("Paddle layout backend requested but unavailable. Falling back to native layout.")

    elif config.layout_backend == "auto":
        provider = PaddleOCRLayoutProvider()
        if provider.is_available():
            return provider

    # Default robust fallback
    return NativeDocLayoutProvider()
