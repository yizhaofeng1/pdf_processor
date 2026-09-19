"""Unit tests for BatchAnalysisWorker and batch analysis pipeline."""

from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

from app.models.question import Question, QuestionType
from app.models.segment import QuestionSegment
from app.pdf.reader import PDFReader
from app.storage.database import save_project_questions
from app.services.detection_service import BatchAnalysisWorker


@pytest.fixture
def pdf_paths():
    p1 = Path(__file__).resolve().parent.parent.parent / "2010_math_test.pdf"
    assert p1.exists(), f"Missing test PDF: {p1}"
    return [p1]


def test_batch_analysis_worker_cached(pdf_paths):
    app = QApplication.instance() or QApplication([])

    pdf_path = pdf_paths[0]
    reader = PDFReader(pdf_path)
    pid = reader.file_hash[:16]
    reader.close()

    # Pre-populate cache in SQLite
    dummy_q = Question(
        display_number="1",
        question_type="选择题",
        source_pdf_path=str(pdf_path),
        source_paper_title=pdf_path.stem,
        segments=[QuestionSegment(page_index=0, normalized_bbox=(0.1, 0.1, 0.9, 0.3))],
    )
    save_project_questions(pid, [dummy_q])

    worker = BatchAnalysisWorker(
        pdf_paths=pdf_paths,
        provider=None,
        skip_cached=True,
    )

    completed_batches = []
    completed_pdfs = []

    worker.pdf_completed.connect(lambda path, qs: completed_pdfs.append((path, qs)))
    worker.batch_finished.connect(lambda res: completed_batches.append(res))

    # Run worker synchronously
    worker.run()

    assert len(completed_pdfs) == 1
    assert completed_pdfs[0][0] == str(pdf_path)
    assert len(completed_pdfs[0][1]) >= 1
    assert completed_pdfs[0][1][0].display_number == "1"
    assert len(completed_batches) == 1


def test_batch_analysis_worker_cancel(pdf_paths):
    app = QApplication.instance() or QApplication([])

    worker = BatchAnalysisWorker(
        pdf_paths=pdf_paths,
        provider=None,
        skip_cached=False,
    )

    cancelled_called = []
    worker.cancelled.connect(lambda: cancelled_called.append(True))

    worker.cancel()
    worker.run()

    assert len(cancelled_called) == 1
