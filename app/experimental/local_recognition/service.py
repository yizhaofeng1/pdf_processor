"""Service orchestration for Local Recognition (VAQL) experiments.

Implements:
1. Virtual Address Pipeline (coarse grounding -> candidate -> local refine -> coordinate projection)
2. Direct Local Baseline Pipeline (whole-page direct bbox prediction)
3. Adapter to convert experiment result to formal Question/QuestionSegment models upon user confirmation.
"""

from typing import List, Dict, Optional, Callable, Tuple
from pathlib import Path
import time
import logging
from datetime import datetime, timezone
from PIL import Image

from .types import (
    LocalRecognitionExperimentResult,
    ExperimentRun,
    CoarsePageOutput,
    CoarseQuestionOutput,
    CandidateRect,
    RefinedQuestionSegment,
    ExperimentMetrics,
)
from .config import LocalVisionConfig
from .provider import LocalVisionProvider, OpenAILocalVisionProvider
from .virtual_address import parse_virtual_address, format_virtual_address
from .page_table import VirtualPageTable
from .tiler import Tiler
from .prompt_builder import ExperimentPromptBuilder
from .candidate_builder import CandidateBuilder
from .local_refiner import LocalRefiner
from .metrics import MetricsCalculator
from .result_store import ResultStore

from ...pdf.reader import PDFReader
from ...pdf.coordinate import normalized_to_pdf_rect
from ...models.question import Question, QuestionType, QuestionStatus
from ...models.segment import QuestionSegment

logger = logging.getLogger("examsplit.experimental.service")


class LocalRecognitionExperimentService:
    """Orchestrates local VLM experiments without altering the core detection pipeline."""

    def __init__(
        self,
        config: Optional[LocalVisionConfig] = None,
        provider: Optional[LocalVisionProvider] = None,
        result_store: Optional[ResultStore] = None,
    ) -> None:
        self.config = config or LocalVisionConfig()
        self.provider = provider or OpenAILocalVisionProvider(self.config)
        self.result_store = result_store or ResultStore()
        self.prompt_builder = ExperimentPromptBuilder()
        self.candidate_builder = CandidateBuilder(
            neighbor_radius=self.config.neighbor_radius,
            overlap_threshold=self.config.candidate_overlap_threshold,
            full_width_layout=getattr(self.config, "full_width_layout", True),
        )
        self.local_refiner = LocalRefiner(
            provider=self.provider,
            prompt_builder=self.prompt_builder,
            local_dpi=self.config.local_dpi,
            max_pixels=getattr(self.config, "max_crop_pixels", 1800000),
        )

    def run_virtual_address_pipeline(
        self,
        reader: PDFReader,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> LocalRecognitionExperimentResult:
        """Execute the full VAQL pipeline: Coarse Grid -> Candidates -> Local Refine -> PDF Coords."""
        start_time = time.time()
        page_count = reader.page_count
        total_steps = page_count * 2 + 2

        run = ExperimentRun(
            source_pdf_hash=reader.file_hash,
            source_pdf_name=reader.pdf_path.name,
            model_provider="local",
            model_name=self.config.model,
            mode="virtual_address",
            grid_rows=self.config.grid_rows,
            grid_columns=self.config.grid_columns,
            neighbor_radius=self.config.neighbor_radius,
            coarse_dpi=self.config.coarse_dpi,
            local_dpi=self.config.local_dpi,
            status="RUNNING",
        )

        def notify(step: int, msg: str) -> None:
            if progress_callback:
                progress_callback(step, total_steps, msg)

        coarse_results: List[CoarsePageOutput] = []
        all_candidates: List[CandidateRect] = []
        all_segments: List[RefinedQuestionSegment] = []
        raw_outputs: List[Dict] = []

        coarse_calls = 0
        local_calls = 0
        input_image_count = 0
        input_image_pixels = 0

        try:
            # 1. Page-level Coarse Localization
            for p_idx in range(page_count):
                if cancel_check and cancel_check():
                    run.status = "CANCELLED"
                    break

                notify(p_idx + 1, f"正在进行第 {p_idx + 1}/{page_count} 页虚拟地址粗定位...")
                p_info = reader.get_page_info(p_idx)
                page_table = VirtualPageTable(
                    page_index=p_idx,
                    page_rect=(0.0, 0.0, p_info.width, p_info.height),
                    rows=self.config.grid_rows,
                    columns=self.config.grid_columns,
                )

                # Render coarse page
                coarse_img_path = Tiler.render_coarse_page(
                    reader,
                    page_index=p_idx,
                    dpi=self.config.coarse_dpi,
                )
                input_image_count += 1
                with Image.open(coarse_img_path) as im:
                    input_image_pixels += im.width * im.height

                # Optionally add grid overlay if configured
                target_img_path = coarse_img_path
                if self.config.send_grid_overlay:
                    target_img_path = Tiler.add_grid_overlay(coarse_img_path, page_table)

                # Build prompt and call local VLM
                prompt = self.prompt_builder.build_coarse_prompt(
                    page_index=p_idx,
                    grid_rows=self.config.grid_rows,
                    grid_columns=self.config.grid_columns,
                    exam_template=getattr(self.config, "exam_template", "kaoyan_math_16"),
                )

                coarse_calls += 1
                try:
                    raw_json = self.provider.analyze_image(target_img_path, prompt)
                    raw_outputs.append({"stage": "coarse", "page": p_idx, "output": raw_json})

                    # Parse and validate schema
                    coarse_page = CoarsePageOutput.model_validate(raw_json)
                    coarse_results.append(coarse_page)

                    # Build candidates for this page
                    page_candidates = self.candidate_builder.build_candidates_for_page(
                        page_table=page_table,
                        coarse_questions=coarse_page.questions,
                    )
                    all_candidates.extend(page_candidates)

                except Exception as e:
                    logger.error(f"Coarse localization failed on page {p_idx}: {e}")
                    raw_outputs.append({"stage": "coarse", "page": p_idx, "error": str(e)})

            # 2. Local High-DPI Refinement
            notify(page_count + 1, f"正在对 {len(all_candidates)} 个候选区域执行局部高精定位...")
            for idx, cand in enumerate(all_candidates):
                if cancel_check and cancel_check():
                    run.status = "CANCELLED"
                    break

                notify(
                    page_count + 1 + int((idx / max(1, len(all_candidates))) * page_count),
                    f"正在精修第 {cand.question_number} 题 (P{cand.page_index + 1})...",
                )

                if not self.config.enable_local_refine:
                    # If refinement is disabled, use candidate bounding box directly
                    doc = reader.doc
                    page = doc[cand.page_index]
                    p_rect = normalized_to_pdf_rect(page.rect, cand.normalized_rect, padding_ratio=(0.0, 0.0))
                    seg = RefinedQuestionSegment(
                        question_number=cand.question_number,
                        page_index=cand.page_index,
                        normalized_bbox=cand.normalized_rect,
                        pdf_bbox=(p_rect.x0, p_rect.y0, p_rect.x1, p_rect.y1),
                        confidence=0.85,
                        boundary_complete=True,
                        source="local_experiment",
                        candidate_rect=cand,
                    )
                    all_segments.append(seg)
                    continue

                local_calls += 1
                input_image_count += 1
                try:
                    seg = self.local_refiner.refine_candidate(reader, cand)
                    all_segments.append(seg)
                except Exception as e:
                    logger.warning(f"Local refine failed for Q{cand.question_number} on page {cand.page_index}: {e}")
                    # Fallback to candidate bounding box
                    doc = reader.doc
                    page = doc[cand.page_index]
                    p_rect = normalized_to_pdf_rect(page.rect, cand.normalized_rect, padding_ratio=(0.0, 0.0))
                    fallback_seg = RefinedQuestionSegment(
                        question_number=cand.question_number,
                        page_index=cand.page_index,
                        normalized_bbox=cand.normalized_rect,
                        pdf_bbox=(p_rect.x0, p_rect.y0, p_rect.x1, p_rect.y1),
                        confidence=0.5,
                        boundary_complete=False,
                        source="local_experiment_fallback",
                        candidate_rect=cand,
                    )
                    all_segments.append(fallback_seg)

            run.status = "SUCCESS" if run.status != "CANCELLED" else "CANCELLED"

        except Exception as e:
            logger.exception("VAQL pipeline failed")
            run.status = "FAILED"
            run.error_message = str(e)

        elapsed = time.time() - start_time
        run.end_time = datetime.now(timezone.utc).isoformat()

        # Compute metrics
        metrics = MetricsCalculator.compute_metrics(
            detected_segments=all_segments,
            coarse_calls=coarse_calls,
            local_calls=local_calls,
            latency_seconds=elapsed,
            input_image_count=input_image_count,
            input_image_pixels=input_image_pixels,
        )

        result = LocalRecognitionExperimentResult(
            run=run,
            coarse_results=coarse_results,
            candidates=all_candidates,
            segments=all_segments,
            metrics=metrics,
            raw_model_outputs=raw_outputs,
        )

        # Save result run to data/experiments/
        self.result_store.save_result(result)
        notify(total_steps, "实验分析完成！")
        return result

    def run_direct_baseline_pipeline(
        self,
        reader: PDFReader,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> LocalRecognitionExperimentResult:
        """Execute the Direct Local Baseline pipeline (whole-page direct bbox prediction)."""
        start_time = time.time()
        page_count = reader.page_count
        total_steps = page_count + 1

        run = ExperimentRun(
            source_pdf_hash=reader.file_hash,
            source_pdf_name=reader.pdf_path.name,
            model_provider="local",
            model_name=self.config.model,
            mode="direct_baseline",
            grid_rows=0,
            grid_columns=0,
            coarse_dpi=self.config.coarse_dpi,
            local_dpi=0,
            status="RUNNING",
        )

        def notify(step: int, msg: str) -> None:
            if progress_callback:
                progress_callback(step, total_steps, msg)

        all_segments: List[RefinedQuestionSegment] = []
        raw_outputs: List[Dict] = []
        calls = 0
        input_image_count = 0
        input_image_pixels = 0

        baseline_prompt = (
            "你是一个试卷题目检测器。请直接检测当前页面中的所有试题。\n"
            "对每道题，输出题号 question_number 和整页归一化边界 bbox: [x1, y1, x2, y2] (范围在 0.0 到 1.0)。\n"
            "请严格以纯 JSON 输出，格式如下：\n"
            "{\n"
            '  "questions": [\n'
            '    {"question_number": "1", "bbox": [0.05, 0.1, 0.95, 0.3], "confidence": 0.9}\n'
            "  ]\n"
            "}"
        )

        try:
            for p_idx in range(page_count):
                if cancel_check and cancel_check():
                    run.status = "CANCELLED"
                    break

                notify(p_idx + 1, f"正在进行第 {p_idx + 1}/{page_count} 页直接定位 Baseline 测试...")
                p_info = reader.get_page_info(p_idx)

                img_path = Tiler.render_coarse_page(
                    reader,
                    page_index=p_idx,
                    dpi=self.config.coarse_dpi,
                )
                input_image_count += 1
                with Image.open(img_path) as im:
                    input_image_pixels += im.width * im.height

                calls += 1
                try:
                    raw_json = self.provider.analyze_image(img_path, baseline_prompt)
                    raw_outputs.append({"stage": "direct_baseline", "page": p_idx, "output": raw_json})

                    qs = raw_json.get("questions", [])
                    for q in qs:
                        q_num = str(q.get("question_number", ""))
                        bbox = q.get("bbox", [0.0, 0.0, 1.0, 1.0])
                        conf = float(q.get("confidence", 1.0))
                        if len(bbox) == 4 and q_num:
                            nx1, ny1, nx2, ny2 = bbox
                            p_rect = normalized_to_pdf_rect(
                                (0.0, 0.0, p_info.width, p_info.height),
                                (nx1, ny1, nx2, ny2),
                                padding_ratio=(0.0, 0.0),
                            )
                            all_segments.append(
                                RefinedQuestionSegment(
                                    question_number=q_num,
                                    page_index=p_idx,
                                    normalized_bbox=(round(nx1, 6), round(ny1, 6), round(nx2, 6), round(ny2, 6)),
                                    pdf_bbox=(round(p_rect.x0, 2), round(p_rect.y0, 2), round(p_rect.x1, 2), round(p_rect.y1, 2)),
                                    confidence=conf,
                                    source="direct_local_baseline",
                                )
                            )
                except Exception as e:
                    logger.error(f"Direct baseline call failed on page {p_idx}: {e}")

            run.status = "SUCCESS" if run.status != "CANCELLED" else "CANCELLED"

        except Exception as e:
            logger.exception("Direct baseline failed")
            run.status = "FAILED"
            run.error_message = str(e)

        elapsed = time.time() - start_time
        run.end_time = datetime.now(timezone.utc).isoformat()

        metrics = MetricsCalculator.compute_metrics(
            detected_segments=all_segments,
            coarse_calls=calls,
            local_calls=0,
            latency_seconds=elapsed,
            input_image_count=input_image_count,
            input_image_pixels=input_image_pixels,
        )

        result = LocalRecognitionExperimentResult(
            run=run,
            segments=all_segments,
            metrics=metrics,
            raw_model_outputs=raw_outputs,
        )

        self.result_store.save_result(result)
        notify(total_steps, "Baseline 分析完成！")
        return result

    @staticmethod
    def apply_experiment_result_to_questions(
        result: LocalRecognitionExperimentResult,
        reader: PDFReader,
    ) -> List[Question]:
        """Explicit adapter: Converts experiment segments to formal Question models.

        Does NOT automatically overwrite; must be called explicitly when user confirms.
        """
        pid = reader.file_hash[:16]
        questions_map: Dict[str, Question] = {}

        # Group segments by question_number
        for seg in result.segments:
            q_num = seg.question_number
            if q_num not in questions_map:
                questions_map[q_num] = Question(
                    project_id=pid,
                    display_number=q_num,
                    original_display_number=q_num,
                    question_type=QuestionType.SMALL,
                    source_pdf_path=str(reader.pdf_path),
                    source_paper_title=reader.pdf_path.stem,
                    segments=[],
                    confidence=seg.confidence,
                    status=QuestionStatus.DETECTED,
                    user_modified=False,
                )

            q_obj = questions_map[q_num]
            q_seg = QuestionSegment(
                question_id=q_obj.id,
                page_index=seg.page_index,
                normalized_bbox=seg.normalized_bbox,
                pdf_bbox=seg.pdf_bbox,
                user_modified=False,
            )
            q_obj.segments.append(q_seg)

        questions = list(questions_map.values())

        # Sort questions numerically if possible
        def _sort_key(q: Question) -> Tuple[int, str]:
            digits = "".join(filter(str.isdigit, q.display_number))
            return (int(digits) if digits else 9999, q.display_number)

        questions.sort(key=_sort_key)
        for idx, q in enumerate(questions):
            q.sort_order = idx
            q.continuation = len(q.segments) > 1

        logger.info(f"Adapted {len(questions)} experimental questions for project {pid}")
        return questions
