"""Service orchestrator for the local AI small-model question segmentation pipeline.

Coordinates the complete mainstream modular pipeline:
1. PyMuPDF Native Page Extraction & Rendering
2. Local Layout Detection (PP-DocLayoutV3 with Native Layout Fallback)
3. Text Extraction & Hybrid OCR Fusion
4. Column & Reading Order Detection
5. Question Marker Detection & Anti-Noise Filtering
6. Candidate Graph & Option Aggregation
7. Deterministic Boundary Resolution (Padding, Option Protection, White-space Trimming)
8. Confidence Evaluation & VLM Routing
9. Local VLM Visual Verification (on borderline/complex candidates)
10. Cross-Page Continuity Resolution
11. Adapter to standard Question/QuestionSegment domain models
"""

import base64
import io
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import pymupdf as fitz  # PyMuPDF

from app.models.question import Question, QuestionStatus, QuestionType
from app.models.segment import QuestionSegment
from ..local_ai.base import LocalLayoutProvider, LocalOCRProvider, LocalVLMProvider
from ..local_ai.config import LocalModelConfig, get_default_config
from ..local_ai.layout_backend import get_layout_provider
from ..local_ai.ocr_backend import get_ocr_provider
from ..local_ai.local_vlm import OpenAILocalVLMProvider
from ..local_ai.types import (
    LayoutElement,
    LocalPageAnalysis,
    LocalQuestionCandidate,
    OCRBlock,
    QuestionMarker,
)
from ..local_detection.boundary_resolver import LocalBoundaryResolver
from ..local_detection.candidate_builder import LocalCandidateBuilder
from ..local_detection.confidence_router import LocalConfidenceRouter
from ..local_detection.cross_page import LocalCrossPageResolver
from ..local_detection.marker_detector import LocalMarkerDetector
from ..local_detection.reading_order import ReadingOrderDetector

logger = logging.getLogger("examsplit.experimental.local_recognition.service")


class LocalAnalysisService:
    """End-to-end service for local exam paper analysis and question extraction."""

    def __init__(
        self,
        config: Optional[LocalModelConfig] = None,
        layout_provider: Optional[LocalLayoutProvider] = None,
        ocr_provider: Optional[LocalOCRProvider] = None,
        vlm_provider: Optional[LocalVLMProvider] = None,
    ) -> None:
        self.config = config or get_default_config()
        self.layout_provider = layout_provider or get_layout_provider(self.config)
        self.ocr_provider = ocr_provider or get_ocr_provider(self.config)
        self.vlm_provider = vlm_provider or OpenAILocalVLMProvider(self.config)

        self.reading_order_detector = ReadingOrderDetector()
        self.marker_detector = LocalMarkerDetector()
        self.candidate_builder = LocalCandidateBuilder()
        self.boundary_resolver = LocalBoundaryResolver(self.config)
        self.confidence_router = LocalConfidenceRouter(self.config)
        self.cross_page_resolver = LocalCrossPageResolver()

    def process_pdf(
        self,
        pdf_path: str,
        page_indices: Optional[List[int]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Tuple[List[Question], Dict[int, LocalPageAnalysis]]:
        """Process a PDF and return formal Question objects along with page analyses.

        Args:
            pdf_path: Absolute path to the PDF file.
            page_indices: Specific 0-indexed pages to process (processes all if None).
            progress_callback: Optional callback receiving (current_step, total_steps, message).

        Returns:
            Tuple of (List of standard Question models, Dict mapping page_index to LocalPageAnalysis).
        """
        pdf_path_str = str(pdf_path)
        doc = fitz.open(pdf_path_str)
        total_doc_pages = len(doc)
        target_pages = page_indices if page_indices is not None else list(range(total_doc_pages))
        total_steps = len(target_pages) * 4 + 2

        candidates_by_page: Dict[int, List[LocalQuestionCandidate]] = {}
        page_analyses: Dict[int, LocalPageAnalysis] = {}
        step = 0

        # Step 1-4: Page-level analysis
        for p_idx in target_pages:
            if p_idx < 0 or p_idx >= total_doc_pages:
                continue

            page = doc[p_idx]
            p_w, p_h = page.rect.width, page.rect.height

            # Step 1: Layout & Text Extraction
            step += 1
            if progress_callback:
                progress_callback(step, total_steps, f"正在分析第 {p_idx + 1} 页版面与文本...")

            layout_elements = self.layout_provider.analyze_page(
                page_image_path=None,
                page_index=p_idx,
                pdf_page=page,
            )

            text_blocks = self.ocr_provider.extract_text_blocks(
                page_image_path=None,
                page_index=p_idx,
                pdf_page=page,
            )

            # Step 2: Reading Order & Column Detection
            step += 1
            if progress_callback:
                progress_callback(step, total_steps, f"正在分析第 {p_idx + 1} 页分栏与阅读顺序...")

            markers = self.marker_detector.detect_markers(text_blocks, page_index=p_idx)
            is_two_col, split_x = self.reading_order_detector.detect_two_column(
                layout_elements or text_blocks,
                markers=markers,
            )

            analysis = LocalPageAnalysis(
                page_index=p_idx,
                layout_elements=layout_elements,
                text_blocks=text_blocks,
                markers=markers,
                is_two_column=is_two_col,
                column_split_x=split_x,
            )
            page_analyses[p_idx] = analysis

            # Step 3: Candidate Assembly & Boundary Resolution
            step += 1
            if progress_callback:
                progress_callback(step, total_steps, f"正在构建第 {p_idx + 1} 页题目候选区域...")

            candidates = self.candidate_builder.build_candidates_for_page(
                page_index=p_idx,
                markers=markers,
                layout_elements=layout_elements,
                text_blocks=text_blocks,
                is_two_column=is_two_col,
                split_x=split_x,
            )

            resolved_candidates = self.boundary_resolver.resolve_candidates(
                candidates,
                is_two_column=is_two_col,
                split_x=split_x or 0.50,
            )

            # Step 4: Confidence Evaluation & Local VLM Review
            step += 1
            if progress_callback:
                progress_callback(step, total_steps, f"正在评估第 {p_idx + 1} 页置信度并进行精修...")

            routed_candidates = self.confidence_router.evaluate_and_route(resolved_candidates)

            # Review uncertain candidates with VLM if applicable
            if self.config.mode != "fast":
                for c in routed_candidates:
                    if c.needs_vlm:
                        self._verify_candidate_with_vlm(page, c, p_w, p_h)

            candidates_by_page[p_idx] = routed_candidates

        # Step 5: Cross-page resolution
        step += 1
        if progress_callback:
            progress_callback(step, total_steps, "正在进行跨页题目连续性分析...")

        all_candidates = self.cross_page_resolver.resolve_cross_page_candidates(
            candidates_by_page,
            page_analyses,
        )

        # Step 6: Convert to formal Question domain models
        step += 1
        if progress_callback:
            progress_callback(step, total_steps, "正在转换为标准试题模型...")

        questions = self.adapt_to_questions(all_candidates, pdf_path_str, Path(pdf_path_str).name)

        doc.close()
        return questions, page_analyses

    def _verify_candidate_with_vlm(
        self,
        page: Any,
        candidate: LocalQuestionCandidate,
        p_w: float,
        p_h: float,
    ) -> None:
        """Render candidate crop and request verification from local VLM."""
        if not candidate.segments:
            return

        seg = candidate.segments[0]
        x0, y0, x1, y1 = seg.bbox
        # Calculate pixel rect in PDF points
        rect = fitz.Rect(x0 * p_w, y0 * p_h, x1 * p_w, y1 * p_h)
        if rect.is_empty or rect.width < 10 or rect.height < 10:
            return

        try:
            # Render crop at 150 DPI
            pix = page.get_pixmap(clip=rect, dpi=150)
            img_bytes = pix.tobytes("jpeg")
            crop_b64 = base64.b64encode(img_bytes).decode("ascii")

            verification = self.vlm_provider.verify_question_region(crop_b64, candidate)
            candidate.vlm_verification = verification

            # If VLM suggests an adjusted bounding box and verification is accepted
            if verification.accept and verification.bbox is not None:
                bx0, by0, bx1, by1 = verification.bbox
                # Validate adjusted bounds are sane
                if 0.0 <= bx0 < bx1 <= 1.0 and 0.0 <= by0 < by1 <= 1.0:
                    seg.bbox = (round(bx0, 4), round(by0, 4), round(bx1, 4), round(by1, 4))
                    candidate.confidence = max(candidate.confidence, verification.confidence)
                    candidate.reasons.append("VLM adjusted boundary accepted")
        except Exception as e:
            logger.warning(f"VLM verification exception for Q{candidate.question_number}: {e}")

    def adapt_to_questions(
        self,
        candidates: List[LocalQuestionCandidate],
        source_pdf_path: Any,
        paper_title: str,
    ) -> List[Question]:
        """Convert LocalQuestionCandidate instances to standard Question domain models."""
        questions: List[Question] = []
        pdf_path_str = str(source_pdf_path) if source_pdf_path is not None else None

        # Sort candidates numerically
        sorted_cand = sorted(
            candidates,
            key=lambda c: int(c.question_number) if c.question_number.isdigit() else 999,
        )

        for sort_order, c in enumerate(sorted_cand):
            segments: List[QuestionSegment] = []
            for seg in c.segments:
                segments.append(
                    QuestionSegment(
                        page_index=seg.page_index,
                        normalized_bbox=seg.bbox,
                    )
                )

            # Determine QuestionType enum
            q_num = int(c.question_number) if c.question_number.isdigit() else 0
            if c.question_type == "choice":
                q_type = QuestionType.CHOICE
            elif c.question_type == "fill_blank":
                q_type = QuestionType.FILL_IN
            elif q_num >= 15 or c.question_type == "solution":
                q_type = QuestionType.SOLVE
            else:
                q_type = QuestionType.SMALL if q_num < 15 else QuestionType.LARGE

            q = Question(
                display_number=c.question_number,
                original_display_number=c.question_number,
                question_type=q_type,
                source_pdf_path=pdf_path_str,
                source_paper_title=paper_title,
                segments=segments,
                continuation=len(segments) > 1,
                confidence=c.confidence,
                review_required=c.needs_vlm or c.confidence < self.config.confidence_threshold,
                selected=True,
                sort_order=sort_order + 1,
                reason_codes=c.reasons,
                status=QuestionStatus.DETECTED,
            )
            questions.append(q)

        return questions
