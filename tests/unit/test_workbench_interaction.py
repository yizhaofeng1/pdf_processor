"""Unit and integration tests for Workbench interaction and bounding box overlays."""

import pytest
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QMessageBox

from app.models.question import Question, QuestionType, QuestionStatus
from app.models.segment import QuestionSegment
from app.ui.pdf_viewer import PDFViewerWidget, QuestionOverlayItem
from app.ui.main_window import MainWindow


@pytest.fixture
def sample_pdf():
    return Path("2010_math_test.pdf").resolve()


def test_pdf_viewer_overlays(qtbot):
    """Test QuestionOverlayItem creation, highlighting, and selection signal."""
    viewer = PDFViewerWidget()
    qtbot.addWidget(viewer)

    # Fake scene dimensions
    viewer.scene.setSceneRect(QRectF(0, 0, 1000, 1400))
    # Fake a pixmap item so set_page_overlays proceeds
    from PySide6.QtGui import QPixmap
    pixmap = QPixmap(1000, 1400)
    viewer._pixmap_item = viewer.scene.addPixmap(pixmap)

    segments_meta = [
        {
            "question_id": "q1",
            "segment_id": "s1",
            "display_number": "1",
            "question_type": "选择题",
            "normalized_bbox": (0.05, 0.10, 0.95, 0.30),
            "review_required": False,
        },
        {
            "question_id": "q2",
            "segment_id": "s2",
            "display_number": "2",
            "question_type": "填空题",
            "normalized_bbox": (0.05, 0.35, 0.95, 0.60),
            "review_required": True,
        },
    ]

    viewer.set_page_overlays(segments_meta, selected_question_id="q1")
    assert len(viewer._segment_overlays) == 2

    ov1 = viewer._segment_overlays[0]
    ov2 = viewer._segment_overlays[1]

    assert ov1.is_selected is True
    assert ov2.is_selected is False
    assert ov2.review_required is True

    # Test highlight_question
    viewer.highlight_question("q2")
    assert ov1.is_selected is False
    assert ov2.is_selected is True

    # Test click signal
    with qtbot.waitSignal(viewer.segment_selected, timeout=1000) as blocker:
        viewer._on_overlay_clicked("q1")
    assert blocker.args == ["q1"]


def test_main_window_question_list_and_details(qtbot, sample_pdf):
    """Test MainWindow loading questions, populating list, updating details panel."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.load_pdf(sample_pdf) is True

    # Manually inject questions into window
    q1 = Question(
        display_number="1",
        question_type=QuestionType.CHOICE,
        segments=[QuestionSegment(page_index=0, normalized_bbox=(0.04, 0.10, 0.96, 0.30))],
        confidence=0.96,
        selected=True,
    )
    q2 = Question(
        display_number="2",
        question_type=QuestionType.SOLVE,
        segments=[
            QuestionSegment(page_index=0, normalized_bbox=(0.04, 0.35, 0.96, 0.85)),
            QuestionSegment(page_index=1, normalized_bbox=(0.04, 0.05, 0.96, 0.40)),
        ],
        continuation=True,
        confidence=0.82,
        review_required=True,
        reason_codes=["OVERLAP_DETECTED"],
        selected=True,
    )

    window.questions = [q1, q2]
    window._populate_question_list()

    assert window.question_list_widget.count() == 2

    # Verify first item selection
    window.question_list_widget.setCurrentRow(0)
    assert window.selected_question == q1
    assert window.lbl_q_number.text() == "第 1 题"
    assert window.lbl_q_type.text() == "选择题"
    assert window.lbl_q_page.text() == "第 1 页"
    assert "96.0%" in window.lbl_q_confidence.text()

    # Switch to question 2 (cross-page & review required)
    window.question_list_widget.setCurrentRow(1)
    assert window.selected_question == q2
    assert window.lbl_q_number.text() == "第 2 题"
    assert window.lbl_q_type.text() == "解答题"
    assert "跨页题" in window.lbl_q_page.text()
    assert window.lbl_q_reasons.isVisible() is True
    assert window.btn_confirm_question.isEnabled() is True

    # Test confirm question
    window._on_confirm_question()
    assert q2.review_required is False
    assert q2.status == QuestionStatus.USER_CONFIRMED
    assert window.lbl_q_reasons.isVisible() is False
    assert window.btn_confirm_question.isEnabled() is False


def test_main_window_selection_operations(qtbot, sample_pdf):
    """Test select all and invert selection operations."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.load_pdf(sample_pdf)

    q1 = Question(display_number="1", segments=[QuestionSegment(page_index=0, normalized_bbox=(0.04, 0.1, 0.96, 0.3))], selected=True)
    q2 = Question(display_number="2", segments=[QuestionSegment(page_index=0, normalized_bbox=(0.04, 0.4, 0.96, 0.7))], selected=True)
    window.questions = [q1, q2]
    window._populate_question_list()

    assert "已选 2 题" in window.status_counts_label.text()
    assert window.tb_export.isEnabled() is True

    # Invert selection -> both unchecked
    window._on_invert_selection()
    assert "已选 0 题" in window.status_counts_label.text()
    assert window.tb_export.isEnabled() is False

    # Select all -> both checked
    window._on_select_all()
    assert "已选 2 题" in window.status_counts_label.text()
    assert window.tb_export.isEnabled() is True


def test_main_window_delete_question_clears_overlays(qtbot, sample_pdf, monkeypatch):
    """Test deleting a question properly clears it from the list, viewer overlays, and details panel."""
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

    window = MainWindow()
    qtbot.addWidget(window)
    window.load_pdf(sample_pdf)

    q1 = Question(
        display_number="1",
        segments=[QuestionSegment(page_index=0, normalized_bbox=(0.04, 0.1, 0.96, 0.3))],
        selected=True,
    )
    window.questions = [q1]
    window._populate_question_list()

    assert len(window.questions) == 1
    assert len(window.pdf_viewer._segment_overlays) == 1
    assert window.selected_question == q1
    assert window.lbl_q_number.text() == "第 1 题"

    # Delete question
    window._on_delete_question(q1.id)

    # Question list and questions must be empty
    assert len(window.questions) == 0
    assert window.question_list_widget.count() == 0

    # Overlays on viewer must be completely cleared
    assert len(window.pdf_viewer._segment_overlays) == 0

    # Detail panel must be reset
    assert window.selected_question is None
    assert window.lbl_q_number.text() == "—"
    assert window.btn_basket_toggle.isEnabled() is False
    assert window.btn_delete_q.isEnabled() is False
