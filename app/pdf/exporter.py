"""PDF Exporter: Lossless A4 question collection export engine.

Follows the Core Principle:
- 100% fidelity: Original PDF is the sole source of truth (read-only).
- Uses PyMuPDF's vector/raster clipping via show_pdf_page without OCR or text re-generation.
- Supports A4 Single-Question-Per-Page (study/practice mode) and A4 Compact Flow (paper-saving mode).
"""

from enum import Enum
from pathlib import Path
from typing import List, Optional, Union
import logging
from datetime import datetime
import pymupdf

from .cropper import A4_WIDTH, A4_HEIGHT, DEFAULT_MARGIN, calculate_fit_rect
from .coordinate import normalized_to_pdf_rect
from ..models.question import Question, QuestionType

logger = logging.getLogger("examsplit.pdf.exporter")

QUESTION_TYPE_NAMES = {
    QuestionType.SMALL: "小题",
    "小题": "小题",
    QuestionType.LARGE: "大题",
    "大题": "大题",
    QuestionType.CHOICE: "选择题",
    "choice": "选择题",
    QuestionType.FILL_IN: "填空题",
    "fill_in": "填空题",
    QuestionType.SOLVE: "解答题",
    "solve": "解答题",
    QuestionType.PROOF: "证明题",
    "proof": "证明题",
    QuestionType.OTHER: "综合题",
    "other": "综合题",
}


class ExportMode(str, Enum):
    """Layout modes for exported PDF."""
    SINGLE_QUESTION_PER_PAGE = "single"  # A4 单题一页 (刷题留白练习模式)
    COMPACT_FLOW = "compact"             # A4 自动紧凑排版 (节约纸张打印模式)
    ADAPTIVE_EXAM_FLOW = "adaptive"      # A4 智能试卷排版 (小题紧凑，大题自适应留白答题区)


class ExportOptions:
    """Configuration options for PDF export."""

    def __init__(
        self,
        mode: ExportMode = ExportMode.ADAPTIVE_EXAM_FLOW,
        paper_title: str = "ExamSplit AI 智能选题集",
        show_header: bool = True,
        show_footer: bool = True,
        margin_pt: float = DEFAULT_MARGIN,
        spacing_pt: float = 20.0,
        show_divider: bool = True,
        large_blank_height_pt: float = 240.0,
        show_answer_box: bool = True,
        renumber_sequentially: bool = False,
        show_source_footnote: bool = True,
    ) -> None:
        self.mode = mode
        self.paper_title = paper_title
        self.show_header = show_header
        self.show_footer = show_footer
        self.margin_pt = margin_pt
        self.spacing_pt = spacing_pt
        self.show_divider = show_divider
        self.large_blank_height_pt = large_blank_height_pt
        self.show_answer_box = show_answer_box
        self.renumber_sequentially = renumber_sequentially
        self.show_source_footnote = show_source_footnote


class PDFExporter:
    """Engine that crops segments from source PDF and places them onto clean A4 pages."""

    @classmethod
    def export(
        cls,
        source_pdf: Union[str, Path],
        questions: List[Question],
        output_path: Union[str, Path],
        options: Optional[ExportOptions] = None,
    ) -> Path:
        """Export selected questions from one or more source PDFs into a lossless A4 PDF."""
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)

        opts = options or ExportOptions()
        selected_qs = [q for q in questions if q.selected]
        if not selected_qs:
            raise ValueError("未选择任何题目，无法导出")

        # Multi-source document cache
        doc_cache: dict[str, pymupdf.Document] = {}
        default_pdf_str = str(source_pdf)
        if Path(default_pdf_str).exists():
            doc_cache[default_pdf_str] = pymupdf.open(default_pdf_str)

        out_doc = pymupdf.open()

        try:
            # Pre-open any distinct source PDFs referenced in questions
            for q in selected_qs:
                p_str = q.source_pdf_path or default_pdf_str
                if p_str and p_str not in doc_cache and Path(p_str).exists():
                    try:
                        doc_cache[p_str] = pymupdf.open(p_str)
                    except Exception as e:
                        logger.warning(f"Failed to open source PDF {p_str}: {e}")

            if opts.mode == ExportMode.SINGLE_QUESTION_PER_PAGE:
                cls._export_single_per_page(doc_cache, default_pdf_str, out_doc, selected_qs, opts)
            elif opts.mode == ExportMode.COMPACT_FLOW:
                cls._export_compact_flow(doc_cache, default_pdf_str, out_doc, selected_qs, opts)
            else:
                cls._export_adaptive_flow(doc_cache, default_pdf_str, out_doc, selected_qs, opts)

            # Apply page numbers in footer once total page count is established
            if opts.show_footer:
                cls._apply_page_footers(out_doc, opts)

            # Save optimized output PDF
            out_doc.save(str(out_file), garbage=3, deflate=True)
            logger.info(f"Export completed: {len(selected_qs)} questions to {out_file} ({len(out_doc)} pages)")
            return out_file
        finally:
            out_doc.close()
            for doc in doc_cache.values():
                try:
                    doc.close()
                except Exception:
                    pass

    @classmethod
    def _export_single_per_page(
        cls,
        doc_cache: dict[str, pymupdf.Document],
        default_pdf: str,
        out_doc: pymupdf.Document,
        questions: List[Question],
        opts: ExportOptions,
    ) -> None:
        """Render each question starting on its own A4 page with optional scratch area."""
        header_h = 40.0 if opts.show_header else 10.0
        footer_h = 35.0 if opts.show_footer else 10.0

        for q_idx, q in enumerate(questions):
            page = out_doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)

            # 1. Header
            if opts.show_header:
                cls._draw_header(page, opts.paper_title, q, q_idx + 1)

            # 2. Content area
            y_start = opts.margin_pt + header_h
            y_max = A4_HEIGHT - opts.margin_pt - footer_h
            avail_w = A4_WIDTH - 2 * opts.margin_pt
            curr_y = y_start

            doc = doc_cache.get(q.source_pdf_path) or doc_cache.get(default_pdf)
            if not doc:
                continue

            for seg_idx, seg in enumerate(q.segments):
                if seg.page_index >= len(doc):
                    continue

                src_page = doc[seg.page_index]
                clip_rect = cls._get_clip_rect(src_page, seg)

                est_h = clip_rect.height
                if curr_y + est_h > y_max and curr_y > y_start + 50:
                    page = out_doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
                    if opts.show_header:
                        cls._draw_header(page, f"{opts.paper_title} (续)", q, q_idx + 1)
                    curr_y = y_start

                target_bounds = pymupdf.Rect(
                    opts.margin_pt,
                    curr_y,
                    opts.margin_pt + avail_w,
                    y_max,
                )

                dest_rect = calculate_fit_rect(clip_rect, target_bounds, max_scale=1.0, align="center")
                page.show_pdf_page(dest_rect, doc, seg.page_index, clip=clip_rect)
                curr_y = dest_rect.y1 + opts.spacing_pt

    @classmethod
    def _export_compact_flow(
        cls,
        doc_cache: dict[str, pymupdf.Document],
        default_pdf: str,
        out_doc: pymupdf.Document,
        questions: List[Question],
        opts: ExportOptions,
    ) -> None:
        """Render questions sequentially down A4 pages, breaking pages only when full."""
        header_h = 36.0 if opts.show_header else 10.0
        footer_h = 35.0 if opts.show_footer else 10.0

        y_start = opts.margin_pt + header_h
        y_max = A4_HEIGHT - opts.margin_pt - footer_h
        avail_w = A4_WIDTH - 2 * opts.margin_pt

        current_page = out_doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
        if opts.show_header:
            cls._draw_header(current_page, opts.paper_title)
        curr_y = y_start

        for q_idx, q in enumerate(questions):
            doc = doc_cache.get(q.source_pdf_path) or doc_cache.get(default_pdf)
            if not doc:
                continue

            for seg in q.segments:
                if seg.page_index >= len(doc):
                    continue

                src_page = doc[seg.page_index]
                clip_rect = cls._get_clip_rect(src_page, seg)

                scale_w = min(1.0, avail_w / max(1.0, clip_rect.width))
                needed_h = clip_rect.height * scale_w + 14.0

                if curr_y + needed_h > y_max and curr_y > y_start + 40:
                    current_page = out_doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
                    if opts.show_header:
                        cls._draw_header(current_page, opts.paper_title)
                    curr_y = y_start

                if opts.show_divider and curr_y > y_start + 5:
                    p1 = pymupdf.Point(opts.margin_pt, curr_y - (opts.spacing_pt / 2.0))
                    p2 = pymupdf.Point(A4_WIDTH - opts.margin_pt, curr_y - (opts.spacing_pt / 2.0))
                    current_page.draw_line(p1, p2, color=(0.82, 0.84, 0.86), width=0.75, dashes="[2 2]")

                target_bounds = pymupdf.Rect(
                    opts.margin_pt,
                    curr_y,
                    opts.margin_pt + avail_w,
                    y_max,
                )

                dest_rect = calculate_fit_rect(clip_rect, target_bounds, max_scale=1.0, align="center")
                current_page.show_pdf_page(dest_rect, doc, seg.page_index, clip=clip_rect)
                curr_y = dest_rect.y1 + opts.spacing_pt

    @classmethod
    def _export_adaptive_flow(
        cls,
        doc_cache: dict[str, pymupdf.Document],
        default_pdf: str,
        out_doc: pymupdf.Document,
        questions: List[Question],
        opts: ExportOptions,
    ) -> None:
        """Render questions with adaptive spacing: compact for small questions, reserved answer area for large questions."""
        header_h = 36.0 if opts.show_header else 10.0
        footer_h = 35.0 if opts.show_footer else 10.0

        y_start = opts.margin_pt + header_h
        y_max = A4_HEIGHT - opts.margin_pt - footer_h
        avail_w = A4_WIDTH - 2 * opts.margin_pt

        current_page = out_doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
        if opts.show_header:
            cls._draw_header(current_page, opts.paper_title)
        curr_y = y_start

        for q_idx, q in enumerate(questions):
            is_large = q.is_large_question()
            blank_h = opts.large_blank_height_pt if is_large else 0.0

            doc = doc_cache.get(q.source_pdf_path) or doc_cache.get(default_pdf)
            if not doc:
                continue

            for seg_idx, seg in enumerate(q.segments):
                if seg.page_index >= len(doc):
                    continue

                src_page = doc[seg.page_index]
                clip_rect = cls._get_clip_rect(src_page, seg)

                scale_w = min(1.0, avail_w / max(1.0, clip_rect.width))
                seg_h = clip_rect.height * scale_w
                is_last_seg = (seg_idx == len(q.segments) - 1)
                needed_h = seg_h + (blank_h if is_last_seg else 0.0) + opts.spacing_pt

                # Smart pagination:
                # If large question + answer space cannot fit on current page,
                # or remaining height is too small (< 180pt for large question, or < needed_h for small question),
                # break to next page.
                min_acceptable_h = min(needed_h, 180.0) if is_large else needed_h
                if curr_y + min_acceptable_h > y_max and curr_y > y_start + 40:
                    current_page = out_doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
                    if opts.show_header:
                        cls._draw_header(current_page, opts.paper_title)
                    curr_y = y_start

                # Draw divider line before question
                if opts.show_divider and curr_y > y_start + 5:
                    p1 = pymupdf.Point(opts.margin_pt, curr_y - (opts.spacing_pt / 2.0))
                    p2 = pymupdf.Point(A4_WIDTH - opts.margin_pt, curr_y - (opts.spacing_pt / 2.0))
                    current_page.draw_line(p1, p2, color=(0.82, 0.84, 0.86), width=0.75, dashes="[2 2]")

                target_bounds = pymupdf.Rect(
                    opts.margin_pt,
                    curr_y,
                    opts.margin_pt + avail_w,
                    y_max,
                )

                dest_rect = calculate_fit_rect(clip_rect, target_bounds, max_scale=1.0, align="center")
                current_page.show_pdf_page(dest_rect, doc, seg.page_index, clip=clip_rect)
                curr_y = dest_rect.y1 + 8.0

                # If this is the last segment of a large question, allocate reserved answer space
                if is_large and is_last_seg and blank_h > 0:
                    answer_top = curr_y
                    answer_bottom = min(y_max, answer_top + blank_h)

                    if opts.show_answer_box and answer_bottom > answer_top + 30:
                        box_rect = pymupdf.Rect(opts.margin_pt, answer_top, opts.margin_pt + avail_w, answer_bottom)
                        current_page.draw_rect(box_rect, color=(0.86, 0.88, 0.91), width=0.6, dashes="[3 3]")
                        current_page.insert_text(
                            pymupdf.Point(opts.margin_pt + 8, answer_top + 14),
                            "【答题草稿区域】",
                            fontname="china-ss",
                            fontsize=8.5,
                            color=(0.68, 0.72, 0.76),
                        )
                    curr_y = answer_bottom + opts.spacing_pt
                else:
                    curr_y = dest_rect.y1 + opts.spacing_pt

    @classmethod
    def _get_clip_rect(cls, page: pymupdf.Page, seg) -> pymupdf.Rect:
        """Resolve clipping rect in PDF points with page boundary clamping."""
        if seg.pdf_bbox and len(seg.pdf_bbox) == 4:
            x0, y0, x1, y1 = seg.pdf_bbox
            r = pymupdf.Rect(x0, y0, x1, y1)
        else:
            r = normalized_to_pdf_rect((0, 0, page.rect.width, page.rect.height), seg.normalized_bbox)

        # Intersect with physical page boundaries
        r = r.intersect(page.rect)
        if r.is_empty or r.width <= 0 or r.height <= 0:
            r = page.rect
        return r

    @classmethod
    def _draw_header(
        cls,
        page: pymupdf.Page,
        title: str,
        question: Optional[Question] = None,
        seq_idx: Optional[int] = None,
    ) -> None:
        """Draw clean top banner with CJK Chinese font support."""
        margin = DEFAULT_MARGIN
        line_y = 38.0

        # Title on left (using built-in Simplified Chinese font china-ss to avoid mojibake)
        page.insert_text(
            pymupdf.Point(margin, 26),
            title,
            fontname="china-ss",
            fontsize=10.5,
            color=(0.2, 0.25, 0.3),
        )

        # Question identifier on right (if single-question mode)
        if question and seq_idx is not None:
            type_name = question.get_type_display_name() if hasattr(question, "get_type_display_name") else QUESTION_TYPE_NAMES.get(question.question_type, "试题")
            orig_num = question.original_display_number or question.display_number
            paper_info = f" · {question.source_paper_title}" if question.source_paper_title else ""
            q_label = f"第 {seq_idx} 题（原第 {orig_num} 题 · {type_name}{paper_info}）"
            try:
                tw = pymupdf.get_text_length(q_label, fontname="china-ss", fontsize=9.5)
            except Exception:
                tw = len(q_label) * 9.5 * 0.75
            page.insert_text(
                pymupdf.Point(max(margin + 100, A4_WIDTH - margin - tw), 26),
                q_label,
                fontname="china-ss",
                fontsize=9.5,
                color=(0.35, 0.4, 0.45),
            )

        # Subtle separator line
        page.draw_line(
            pymupdf.Point(margin, line_y),
            pymupdf.Point(A4_WIDTH - margin, line_y),
            color=(0.85, 0.88, 0.90),
            width=0.75,
        )

    @classmethod
    def _apply_page_footers(cls, doc: pymupdf.Document, opts: ExportOptions) -> None:
        """Stamp footer and page numbers across all pages."""
        total = len(doc)
        margin = opts.margin_pt
        foot_y = A4_HEIGHT - 22.0

        for idx, page in enumerate(doc):
            # Left watermark/brand
            page.insert_text(
                pymupdf.Point(margin, foot_y),
                "ExamSplit AI 生成",
                fontname="china-ss",
                fontsize=8.5,
                color=(0.55, 0.6, 0.65),
            )

            # Center/Right page numbering: "第 X 页 / 共 Y 页"
            page_str = f"第 {idx + 1} 页 / 共 {total} 页"
            try:
                pw = pymupdf.get_text_length(page_str, fontname="china-ss", fontsize=8.5)
            except Exception:
                pw = len(page_str) * 8.5 * 0.75
            page.insert_text(
                pymupdf.Point(A4_WIDTH - margin - pw, foot_y),
                page_str,
                fontname="china-ss",
                fontsize=8.5,
                color=(0.55, 0.6, 0.65),
            )
