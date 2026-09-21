"""Unit tests for Batch Basket Add, PDF Overlay Isolation, Dense Large Questions, and Paper Templates."""

import pytest
import tempfile
import shutil
from pathlib import Path
import fitz
from PySide6.QtWidgets import QApplication

from app.services.question_basket import GLOBAL_BASKET
from app.models.question import Question, QuestionType, QuestionStatus, AnchorPoint
from app.models.segment import QuestionSegment
from app.detection.marker_detector import QuestionMarker
from app.detection.boundary_resolver import BoundaryResolver
from app.storage.paper_template import PaperTemplateStorage, BUILTIN_TEMPLATES
from app.ai.prompt_manager import PromptManager
from app.ui.main_window import MainWindow
from app.pdf.reader import PDFReader


@pytest.fixture(autouse=True)
def clean_basket():
    GLOBAL_BASKET.clear()
    yield
    GLOBAL_BASKET.clear()


def test_batch_add_to_basket():
    """Test batch adding multiple checked questions to GLOBAL_BASKET."""
    q1 = Question(id="q1", display_number="1", question_type=QuestionType.CHOICE)
    q2 = Question(id="q2", display_number="2", question_type=QuestionType.CHOICE)
    q3 = Question(id="q3", display_number="3", question_type=QuestionType.FILL_IN)

    added = GLOBAL_BASKET.add_questions([q1, q2, q3])
    assert added == 3
    assert GLOBAL_BASKET.count() == 3

    # Adding again should update rather than duplicate
    added_again = GLOBAL_BASKET.add_questions([q2, q3])
    assert added_again == 0
    assert GLOBAL_BASKET.count() == 3


def test_prompt_manager_injects_paper_structure():
    """Test that PromptManager correctly embeds paper_structure from context_hints."""
    hint = "第1~10题为单选题；第11~16题为填空题；第17~22题为解答题。"
    prompt = PromptManager.get_system_prompt("detect_markers", context_hints={"paper_structure": hint})
    assert "【用户指定的本卷结构大纲分布（重要裁决依据）】" in prompt
    assert hint in prompt


def test_paper_template_storage_lifecycle(tmp_path, monkeypatch):
    """Test saving, loading, and deleting custom templates."""
    test_tpl_file = tmp_path / "paper_templates.json"
    test_pref_file = tmp_path / "template_preference.json"
    monkeypatch.setattr("app.storage.paper_template.TEMPLATE_FILE", test_tpl_file)
    monkeypatch.setattr("app.storage.paper_template.PREFERENCE_FILE", test_pref_file)

    # 1. Built-in templates exist
    builtins = PaperTemplateStorage.get_builtin_templates()
    assert "2021~至今 考研数学 (一/二/三)" in builtins
    assert PaperTemplateStorage.is_builtin("2021~至今 考研数学 (一/二/三)")

    # 2. Save custom template
    PaperTemplateStorage.save_custom_template("测试自命题数学", "1-5题选择，6-10题大题")
    customs = PaperTemplateStorage.get_custom_templates()
    assert "测试自命题数学" in customs
    assert customs["测试自命题数学"] == "1-5题选择，6-10题大题"
    assert not PaperTemplateStorage.is_builtin("测试自命题数学")

    all_tpls = PaperTemplateStorage.get_all_templates()
    assert "测试自命题数学" in all_tpls

    # 3. Setting active template
    PaperTemplateStorage.set_active_template_name("测试自命题数学")
    assert PaperTemplateStorage.get_active_template_name() == "测试自命题数学"

    # 4. Delete custom template
    deleted = PaperTemplateStorage.delete_custom_template("测试自命题数学")
    assert deleted is True
    assert "测试自命题数学" not in PaperTemplateStorage.get_custom_templates()


def test_dense_large_question_ai_first():
    """Test that dense large questions trust AI boundaries without aggressive local text expansion."""
    resolver = BoundaryResolver()

    # Create two large questions packed tightly on one page (e.g. Q17 and Q18)
    # AI returned precise visual bboxes:
    # Q17: y from 0.10 to 0.28 (height 0.18, dense!)
    # Q18: y from 0.30 to 0.48 (height 0.18, dense!)
    m1 = QuestionMarker(
        number="17",
        page_index=0,
        normalized_point=(0.05, 0.10),
        normalized_bbox=(0.05, 0.10, 0.95, 0.28),
        question_type=QuestionType.SOLVE,
    )
    m2 = QuestionMarker(
        number="18",
        page_index=0,
        normalized_point=(0.05, 0.30),
        normalized_bbox=(0.05, 0.30, 0.95, 0.48),
        question_type=QuestionType.SOLVE,
    )

    # Suppose there are text blocks extending all the way down to y=0.295 in Q17
    text_blocks = [
        (50, 100, 500, 150, "17. (本小题满分10分)", 0, 0),
        (50, 160, 500, 240, "计算极限：lim_{x->0} ...", 0, 0),
        (50, 245, 500, 290, "额外草稿或注释文本", 0, 0),
    ]

    questions = resolver.resolve_page_questions(
        markers=[m1, m2],
        page_index=0,
        page_width=1000.0,
        page_height=1000.0,
        text_blocks=text_blocks,
    )

    assert len(questions) == 2
    q17 = questions[0]
    seg17 = q17.segments[0]

    # Q17 should be recognized as dense large question and preserved to AI's bbox ~0.28,
    # strictly not exceeding next question's top boundary and not expanded downwards arbitrarily
    assert seg17.normalized_bbox[1] == pytest.approx(0.10, abs=0.01)
    assert seg17.normalized_bbox[3] <= 0.30


def test_pdf_overlay_isolation(qtbot):
    """Test QuestionOverlayItem cleanup via clear_overlays."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPixmap
    from app.ui.pdf_viewer import PDFViewerWidget

    viewer = PDFViewerWidget()
    qtbot.addWidget(viewer)
    viewer.scene.setSceneRect(QRectF(0, 0, 1000, 1400))
    viewer._pixmap_item = viewer.scene.addPixmap(QPixmap(1000, 1400))

    viewer.set_page_overlays([{
        "question_id": "q1",
        "segment_id": "s1",
        "display_number": "1",
        "question_type": "选择题",
        "normalized_bbox": (0.1, 0.1, 0.9, 0.3),
        "review_required": False,
    }])
    assert len(viewer._segment_overlays) == 1

    # Verify clear_overlays clears both internal tracker and scene items
    viewer.clear_overlays()
    assert len(viewer._segment_overlays) == 0



