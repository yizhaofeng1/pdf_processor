"""Unit tests for Chinese font configuration and Chinese filename handling."""

from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from app.ui.font_helper import setup_application_fonts, PREFERRED_FAMILIES
from app.pdf.reader import PDFReader, validate_pdf
from app.ui.main_window import MainWindow

CHINESE_PDF = Path(__file__).resolve().parent.parent.parent / "2010考研数一真题解析.pdf"


def test_font_helper_configuration(qtbot):
    """Verify application font configuration picks up CJK families without error."""
    app = QApplication.instance() or QApplication([])
    setup_application_fonts(app)

    font = app.font()
    assert font is not None
    # Check that preferred fallback list is configured
    assert len(font.families()) > 0


def test_chinese_filename_loading(qtbot):
    """Verify PDF files with Chinese names can be validated, opened, and rendered."""
    assert CHINESE_PDF.exists(), f"Missing Chinese test file: {CHINESE_PDF}"

    # 1. Validation test
    val_res = validate_pdf(CHINESE_PDF)
    assert val_res.is_valid is True
    assert val_res.page_count == 8

    # 2. PDFReader test
    with PDFReader(CHINESE_PDF) as reader:
        assert reader.page_count == 8
        assert reader.file_path.name == "2010考研数一真题解析.pdf"

    # 3. MainWindow integration test
    window = MainWindow(initial_pdf=CHINESE_PDF)
    qtbot.addWidget(window)

    assert "2010考研数一真题解析.pdf" in window.windowTitle()
    assert "2010考研数一真题解析.pdf" in window.status_file_label.text()
    assert window.pdf_viewer._page_count == 8
