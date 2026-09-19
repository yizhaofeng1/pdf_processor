"""Detection Service: Orchestrates page rendering, marker detection,
boundary derivation, cross-page resolution, consistency checking, and persistence.
"""

from typing import Optional, Callable, List, Dict
import logging
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from ..pdf.reader import PDFReader, PageType
from ..pdf.coordinate import normalized_to_pdf_rect
from ..models.question import Question
from ..models.segment import QuestionSegment
from ..detection.marker_detector import (
    HybridMarkerDetector,
    AIMarkerDetector,
    NativeTextMarkerDetector,
    QuestionMarker,
)
from ..detection.boundary_resolver import BoundaryResolver
from ..detection.cross_page_resolver import CrossPageResolver
from ..detection.consistency import ConsistencyChecker
from ..storage.database import save_project_questions, load_project_questions

logger = logging.getLogger("examsplit.services.detection")


class DetectionService:
    """Full-pipeline orchestration service for question segmentation."""

    def __init__(
        self,
        provider=None,
        boundary_resolver: Optional[BoundaryResolver] = None,
        cross_page_resolver: Optional[CrossPageResolver] = None,
        consistency_checker: Optional[ConsistencyChecker] = None,
    ) -> None:
        self.provider = provider
        self.boundary_resolver = boundary_resolver or BoundaryResolver()
        self.cross_page_resolver = cross_page_resolver or CrossPageResolver()
        self.consistency_checker = consistency_checker or ConsistencyChecker()

    def run_pipeline(
        self,
        reader: PDFReader,
        project_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> List[Question]:
        """Execute full end-to-end question detection pipeline."""
        page_count = reader.page_count
        total_steps = page_count + 3
        pid = project_id or reader.file_hash[:16]

        def notify(step: int, msg: str) -> None:
            if progress_callback:
                progress_callback(step, total_steps, msg)

        # 1. Setup marker detector
        ai_detector = AIMarkerDetector(self.provider) if self.provider else None
        hybrid_detector = HybridMarkerDetector(reader, ai_detector=ai_detector)

        page_questions_map: Dict[int, List[Question]] = {}

        # 2. Process each page individually
        for p_idx in range(page_count):
            if cancel_check and cancel_check():
                logger.info("Pipeline cancelled by user during page processing.")
                return []

            page_info = reader.get_page_info(p_idx)
            notify(p_idx + 1, f"正在分析第 {p_idx + 1} / {page_count} 页结构与题目...")

            markers = hybrid_detector.detect_page(p_idx)

            # Extract native text blocks if available for high-precision boundary snapping
            text_blocks = None
            if page_info.page_type != PageType.IMAGE_PDF:
                try:
                    page = reader.get_page(p_idx)
                    text_blocks = page.get_text("blocks")
                except Exception as e:
                    logger.debug(f"Failed to extract text blocks on page {p_idx}: {e}")
                    text_blocks = None

            page_qs = self.boundary_resolver.resolve_page_questions(
                markers,
                page_index=p_idx,
                page_width=page_info.width,
                page_height=page_info.height,
                text_blocks=text_blocks,
            )

            # Pre-calculate pdf_bbox for each segment and populate source metadata
            for q in page_qs:
                q.project_id = pid
                if not q.source_pdf_path:
                    q.source_pdf_path = str(reader.pdf_path)
                if not q.source_paper_title:
                    q.source_paper_title = reader.pdf_path.stem
                if not q.original_display_number:
                    q.original_display_number = q.display_number

                for seg in q.segments:
                    p_rect = normalized_to_pdf_rect(
                        (0.0, 0.0, page_info.width, page_info.height),
                        seg.normalized_bbox,
                    )
                    seg.pdf_bbox = (p_rect.x0, p_rect.y0, p_rect.x1, p_rect.y1)

            page_questions_map[p_idx] = page_qs

        if cancel_check and cancel_check():
            logger.info("Pipeline cancelled before cross-page resolution.")
            return []

        # 3. Cross-page resolution
        notify(page_count + 1, "正在校验与合并跨页题目...")
        all_questions = self.cross_page_resolver.resolve(page_questions_map, page_count)

        # Ensure all segments (including merged continuations) have pdf_bbox and source metadata
        for q in all_questions:
            if not q.source_pdf_path:
                q.source_pdf_path = str(reader.pdf_path)
            if not q.source_paper_title:
                q.source_paper_title = reader.pdf_path.stem
            if not q.original_display_number:
                q.original_display_number = q.display_number

            for seg in q.segments:
                if not seg.pdf_bbox and seg.page_index < page_count:
                    p_info = reader.get_page_info(seg.page_index)
                    p_rect = normalized_to_pdf_rect(
                        (0.0, 0.0, p_info.width, p_info.height),
                        seg.normalized_bbox,
                    )
                    seg.pdf_bbox = (p_rect.x0, p_rect.y0, p_rect.x1, p_rect.y1)

        # 4. Consistency checks
        notify(page_count + 2, "正在执行本地几何与题号一致性校验...")
        checked_questions = self.consistency_checker.check(all_questions)

        # 5. Persist to SQLite
        notify(page_count + 3, f"正在保存分析结果 (已识别 {len(checked_questions)} 道题)...")
        try:
            save_project_questions(pid, checked_questions)
        except Exception as e:
            logger.warning(f"Failed to persist questions to database: {e}")

        logger.info(f"Pipeline completed successfully. Total questions: {len(checked_questions)}")
        return checked_questions


class AnalysisWorker(QThread):
    """Background worker thread executing the detection pipeline without blocking UI."""

    progress = Signal(int, int, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        reader: PDFReader,
        provider=None,
        project_id: Optional[str] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.reader = reader
        self.provider = provider
        self.project_id = project_id
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            service = DetectionService(provider=self.provider)
            questions = service.run_pipeline(
                reader=self.reader,
                project_id=self.project_id,
                progress_callback=lambda cur, tot, msg: self.progress.emit(cur, tot, msg),
                cancel_check=lambda: self._is_cancelled,
            )
            self.finished.emit(questions)
        except Exception as e:
            logger.exception("Analysis worker failed")
            self.error.emit(str(e))


class BatchAnalysisWorker(QThread):
    """Background worker thread executing batch detection across multiple PDF files."""

    progress_updated = Signal(str, int, int, int, int)  # (current_pdf_name, pdf_idx, total_pdfs, page_idx, total_pages)
    pdf_completed = Signal(str, list)                   # (pdf_path, questions)
    batch_finished = Signal(dict)                       # {pdf_path: questions}
    pdf_error = Signal(str, str)                        # (pdf_path, error_msg)
    cancelled = Signal()

    def __init__(
        self,
        pdf_paths: List[Path],
        provider=None,
        skip_cached: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.pdf_paths = [Path(p) for p in pdf_paths]
        self.provider = provider
        self.skip_cached = skip_cached
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        results: Dict[str, List[Question]] = {}
        total_pdfs = len(self.pdf_paths)

        for pdf_idx, pdf_path in enumerate(self.pdf_paths):
            if self._is_cancelled:
                self.cancelled.emit()
                return

            pdf_str = str(pdf_path)
            try:
                reader = PDFReader(pdf_path)
                pid = reader.file_hash[:16]

                # Check cache if requested
                if self.skip_cached:
                    cached_qs = load_project_questions(pid)
                    if cached_qs:
                        logger.info(f"Loaded {len(cached_qs)} cached questions for {pdf_path.name}")
                        results[pdf_str] = cached_qs
                        self.progress_updated.emit(pdf_path.name, pdf_idx + 1, total_pdfs, reader.page_count, reader.page_count)
                        self.pdf_completed.emit(pdf_str, cached_qs)
                        reader.close()
                        continue

                service = DetectionService(provider=self.provider)

                def _progress_cb(cur: int, tot: int, msg: str) -> None:
                    self.progress_updated.emit(pdf_path.name, pdf_idx + 1, total_pdfs, cur, tot)

                questions = service.run_pipeline(
                    reader=reader,
                    project_id=pid,
                    progress_callback=_progress_cb,
                    cancel_check=lambda: self._is_cancelled,
                )
                reader.close()

                if self._is_cancelled:
                    self.cancelled.emit()
                    return

                results[pdf_str] = questions
                self.pdf_completed.emit(pdf_str, questions)

            except Exception as e:
                logger.exception(f"Failed to analyze PDF in batch: {pdf_path}")
                self.pdf_error.emit(pdf_str, str(e))

        if self._is_cancelled:
            self.cancelled.emit()
        else:
            self.batch_finished.emit(results)
