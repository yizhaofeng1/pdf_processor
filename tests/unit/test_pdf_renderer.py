"""Unit tests for PDF rendering and rasterization."""

from pathlib import Path
from PySide6.QtGui import QPixmap, QImage
from PIL import Image

from app.pdf.reader import PDFReader
from app.pdf.renderer import (
    PDFRenderer,
    pixmap_to_qimage,
    pixmap_to_qpixmap,
)

TEST_PDF = Path(__file__).resolve().parent.parent.parent / "2010_math_test.pdf"


def test_render_page_to_pixmap():
    """Verify rendering produces expected pixel dimensions matching DPI."""
    with PDFReader(TEST_PDF) as reader:
        # At 72 DPI, 1 point == 1 pixel
        pix_72 = PDFRenderer.render_page_to_pixmap(reader, 0, dpi=72)
        assert pix_72.width > 500
        assert pix_72.height > 800

        # At 144 DPI (double resolution)
        pix_144 = PDFRenderer.render_page_to_pixmap(reader, 0, dpi=144)
        assert abs(pix_144.width - pix_72.width * 2) <= 2
        assert abs(pix_144.height - pix_72.height * 2) <= 2


def test_render_page_to_qpixmap():
    """Verify PySide6 QPixmap conversion."""
    with PDFReader(TEST_PDF) as reader:
        qpix = PDFRenderer.render_page_to_qpixmap(reader, 0, dpi=100)
        assert isinstance(qpix, QPixmap)
        assert not qpix.isNull()
        assert qpix.width() > 0
        assert qpix.height() > 0


def test_render_page_to_image_file(tmp_path: Path):
    """Verify rendering and saving to PNG on disk."""
    out_img = tmp_path / "page_0.png"
    with PDFReader(TEST_PDF) as reader:
        saved_path = PDFRenderer.render_page_to_image_file(reader, 0, out_img, dpi=100)
        assert saved_path.exists()
        assert saved_path.stat().st_size > 0

        # Verify with PIL
        with Image.open(saved_path) as pil_img:
            assert pil_img.width > 500
            assert pil_img.height > 800


def test_generate_thumbnail(tmp_path: Path):
    """Verify thumbnail generation respects max bounding size."""
    thumb_path = tmp_path / "thumb_0.png"
    with PDFReader(TEST_PDF) as reader:
        saved_thumb = PDFRenderer.generate_thumbnail(reader, 0, thumb_path, max_size=200)
        assert saved_thumb.exists()

        with Image.open(saved_thumb) as pil_img:
            assert max(pil_img.width, pil_img.height) <= 200
