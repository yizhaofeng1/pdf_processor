"""Local Refiner: High-resolution local boundary refinement using local VLM and coordinate projection."""

from pathlib import Path
from typing import Tuple, Optional, Union
import pymupdf
import logging

from .types import CandidateRect, LocalRefineOutput, RefinedQuestionSegment
from .provider import LocalVisionProvider
from .prompt_builder import ExperimentPromptBuilder
from .tiler import Tiler
from ...pdf.reader import PDFReader
from ...pdf.coordinate import normalized_to_pdf_rect, clamp

logger = logging.getLogger("examsplit.experimental.local_refiner")


class LocalRefiner:
    """Refines candidate bounding boxes by analyzing high-DPI crops with the local VLM."""

    def __init__(
        self,
        provider: LocalVisionProvider,
        prompt_builder: Optional[ExperimentPromptBuilder] = None,
        local_dpi: int = 250,
        max_pixels: int = 1800000,
    ) -> None:
        self.provider = provider
        self.prompt_builder = prompt_builder or ExperimentPromptBuilder()
        self.local_dpi = local_dpi
        self.max_pixels = max_pixels

    def refine_candidate(
        self,
        reader_or_doc: Union[PDFReader, pymupdf.Document],
        candidate: CandidateRect,
    ) -> RefinedQuestionSegment:
        """Render high-DPI crop of candidate, invoke local VLM, and map coordinates back to full page & PDF."""
        # 1. Render high-DPI crop directly from PDF
        crop_path = Tiler.crop_candidate_high_res(
            reader_or_doc,
            page_index=candidate.page_index,
            normalized_rect=candidate.normalized_rect,
            dpi=self.local_dpi,
            max_pixels=self.max_pixels,
        )

        # 2. Build refine prompt
        prompt = self.prompt_builder.build_local_refine_prompt(
            question_number=candidate.question_number,
        )

        # 3. Call local VLM
        raw_json = self.provider.analyze_image(crop_path, prompt)

        # 4. Parse output
        refine_output = LocalRefineOutput.model_validate(raw_json)

        # 5. Transform local crop normalized bbox -> full page normalized bbox
        cx1, cy1, cx2, cy2 = candidate.normalized_rect
        cw = cx2 - cx1
        ch = cy2 - cy1

        lx1, ly1, lx2, ly2 = refine_output.bbox

        fx1 = clamp(cx1 + lx1 * cw, 0.0, 1.0)
        fy1 = clamp(cy1 + ly1 * ch, 0.0, 1.0)
        fx2 = clamp(cx1 + lx2 * cw, 0.0, 1.0)
        fy2 = clamp(cy1 + ly2 * ch, 0.0, 1.0)

        if fx1 > fx2:
            fx1, fx2 = fx2, fx1
        if fy1 > fy2:
            fy1, fy2 = fy2, fy1

        # 6. Map to PDF coordinates
        doc = reader_or_doc.doc if isinstance(reader_or_doc, PDFReader) else reader_or_doc
        page = doc[candidate.page_index]
        pdf_rect = normalized_to_pdf_rect(page.rect, (fx1, fy1, fx2, fy2), padding_ratio=(0.0, 0.0))

        return RefinedQuestionSegment(
            question_number=candidate.question_number,
            page_index=candidate.page_index,
            normalized_bbox=(round(fx1, 6), round(fy1, 6), round(fx2, 6), round(fy2, 6)),
            pdf_bbox=(round(pdf_rect.x0, 2), round(pdf_rect.y0, 2), round(pdf_rect.x1, 2), round(pdf_rect.y1, 2)),
            confidence=refine_output.confidence,
            boundary_complete=refine_output.boundary_complete,
            source="local_experiment",
            candidate_rect=candidate,
        )
