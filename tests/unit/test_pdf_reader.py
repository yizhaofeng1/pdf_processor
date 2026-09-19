"""Unit tests for PDF reader and validation."""

import pytest
from pathlib import Path
from app.pdf.reader import PDFReader, validate_pdf, compute_file_hash
from app.models.page import PageType

TEST_PDF = Path(__file__).resolve().parent.parent.parent / "2010_math_test.pdf"


def test_validate_pdf_success():
    """Verify test PDF passes validation with expected properties."""
    assert TEST_PDF.exists(), f"Test PDF missing: {TEST_PDF}"
    result = validate_pdf(TEST_PDF)
    assert result.is_valid is True
    assert result.error_message is None
    assert result.page_count == 8
    assert result.is_encrypted is False
    assert result.file_size_bytes > 0


def test_validate_pdf_not_found(tmp_path: Path):
    """Verify non-existent file returns invalid result."""
    fake_pdf = tmp_path / "non_existent.pdf"
    result = validate_pdf(fake_pdf)
    assert result.is_valid is False
    assert "不存在" in (result.error_message or "")


def test_validate_pdf_invalid_extension(tmp_path: Path):
    """Verify non-pdf extension is rejected."""
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello World", encoding="utf-8")
    result = validate_pdf(txt_file)
    assert result.is_valid is False
    assert "扩展名" in (result.error_message or "")


def test_validate_pdf_empty_file(tmp_path: Path):
    """Verify 0-byte file is rejected as corrupted."""
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.touch()
    result = validate_pdf(empty_pdf)
    assert result.is_valid is False
    assert "0 字节" in (result.error_message or "")


def test_compute_file_hash():
    """Verify SHA-256 calculation produces 64 hex characters."""
    file_hash = compute_file_hash(TEST_PDF)
    assert isinstance(file_hash, str)
    assert len(file_hash) == 64
    # Recomputing produces deterministic output
    assert compute_file_hash(TEST_PDF) == file_hash


def test_pdf_reader_lifecycle():
    """Verify PDFReader opens document, extracts dimensions, page info and closes."""
    with PDFReader(TEST_PDF) as reader:
        assert reader.page_count == 8
        assert reader.file_hash is not None

        # Check page rect
        rect = reader.get_page_rect(0)
        assert rect[0] == 0.0
        assert rect[1] == 0.0
        assert rect[2] > 500  # Approx 595 pt for A4
        assert rect[3] > 800  # Approx 842 pt for A4

        # Check page type (scanned image PDF)
        page_type = reader.detect_page_type(0)
        assert page_type == PageType.IMAGE_PDF

        # Check structured PageInfo
        info = reader.get_page_info(0, project_id="test_proj")
        assert info.page_index == 0
        assert info.project_id == "test_proj"
        assert info.rotation == 0
        assert info.page_type == PageType.IMAGE_PDF

        # Check out-of-range index
        with pytest.raises(IndexError):
            reader.get_page(100)
