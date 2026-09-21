"""Unit and pipeline integration tests for LocalRecognitionExperimentService with Mock Provider."""

from pathlib import Path
from typing import Dict, Any, Tuple, List
import pymupdf

from app.experimental.local_recognition.config import LocalVisionConfig
from app.experimental.local_recognition.provider import LocalVisionProvider
from app.experimental.local_recognition.service import LocalRecognitionExperimentService
from app.experimental.local_recognition.result_store import ResultStore
from app.pdf.reader import PDFReader


class MockLocalVisionProvider(LocalVisionProvider):
    """Mock provider simulating deterministic responses for coarse and refine stages."""

    def test_connection(self) -> Tuple[bool, str]:
        return True, "Mock connected"

    def fetch_available_models(self) -> List[str]:
        return ["mock-vlm-0.5b", "mock-vlm-7b"]

    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        system_instruction: str | None = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        if "vaql-coarse" in prompt or "虚拟区域网格" in prompt:
            # Coarse response
            return {
                "schema_version": "vaql-coarse-v1",
                "page_index": 0,
                "questions": [
                    {
                        "question_number": "1",
                        "regions": ["P00:R01:C00", "P00:R01:C01"],
                        "confidence": 0.95,
                        "cross_page": False,
                    },
                    {
                        "question_number": "2",
                        "regions": ["P00:R03:C00", "P00:R03:C01", "P00:R04:C00"],
                        "confidence": 0.92,
                        "cross_page": False,
                    },
                ],
            }
        elif "vaql-local" in prompt or "真实完整物理外轮廓" in prompt:
            # Local refine response
            return {
                "schema_version": "vaql-local-v1",
                "question_number": "1",
                "bbox": [0.05, 0.05, 0.95, 0.95],
                "confidence": 0.96,
                "boundary_complete": True,
                "needs_neighbor": False,
            }
        else:
            # Baseline prompt
            return {
                "questions": [
                    {"question_number": "1", "bbox": [0.05, 0.1, 0.95, 0.3], "confidence": 0.9},
                    {"question_number": "2", "bbox": [0.05, 0.35, 0.95, 0.6], "confidence": 0.9},
                ]
            }


def test_virtual_address_pipeline(tmp_path):
    # 1. Create a dummy 1-page PDF
    pdf_path = tmp_path / "test_exam.pdf"
    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    p.draw_rect(pymupdf.Rect(50, 50, 500, 200), color=(0, 0, 1))
    doc.save(str(pdf_path))
    doc.close()

    reader = PDFReader(pdf_path)

    # 2. Setup service with mock provider and isolated result store
    cfg = LocalVisionConfig(grid_rows=8, grid_columns=4, neighbor_radius=0)
    provider = MockLocalVisionProvider(cfg)
    store = ResultStore(base_dir=tmp_path / "runs")
    service = LocalRecognitionExperimentService(config=cfg, provider=provider, result_store=store)

    # 3. Execute VAQL pipeline
    result = service.run_virtual_address_pipeline(reader)

    assert result.run.status == "SUCCESS"
    assert len(result.coarse_results) == 1
    assert len(result.candidates) == 2
    assert len(result.segments) == 2
    assert result.metrics.total_questions_detected == 2
    assert result.metrics.coarse_calls == 1
    assert result.metrics.local_calls == 2

    # Check persistence
    assert (tmp_path / "runs" / result.run.run_id / "run.json").exists()
    assert (tmp_path / "runs" / result.run.run_id / "summary.md").exists()

    # 4. Test adapter to formal Question models
    questions = LocalRecognitionExperimentService.apply_experiment_result_to_questions(result, reader)
    assert len(questions) == 2
    assert questions[0].display_number == "1"
    assert questions[1].display_number == "2"
    assert questions[0].user_modified is False
    assert len(questions[0].segments) == 1
    assert questions[0].segments[0].pdf_bbox is not None

    reader.close()


def test_direct_baseline_pipeline(tmp_path):
    pdf_path = tmp_path / "test_exam_baseline.pdf"
    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    doc.save(str(pdf_path))
    doc.close()

    reader = PDFReader(pdf_path)

    cfg = LocalVisionConfig()
    provider = MockLocalVisionProvider(cfg)
    store = ResultStore(base_dir=tmp_path / "runs")
    service = LocalRecognitionExperimentService(config=cfg, provider=provider, result_store=store)

    result = service.run_direct_baseline_pipeline(reader)

    assert result.run.status == "SUCCESS"
    assert result.run.mode == "direct_baseline"
    assert len(result.segments) == 2
    assert result.metrics.coarse_calls == 1
    assert result.metrics.local_calls == 0

    reader.close()
