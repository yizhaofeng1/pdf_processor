"""PDF Rendering and rasterization engine for UI display and AI processing."""

from pathlib import Path
from typing import Union
import pymupdf
from PySide6.QtGui import QImage, QPixmap
from PIL import Image
import io

from .reader import PDFReader
from ..config import DEFAULT_RENDER_DPI, THUMBNAILS_DIR


def pixmap_to_qimage(pix: pymupdf.Pixmap) -> QImage:
    """Convert a PyMuPDF Pixmap to a standalone PySide6 QImage with deep memory copy."""
    # Ensure standard color space (RGB or RGBA)
    if pix.colorspace.n == 1:
        # Grayscale
        img_format = QImage.Format.Format_Grayscale8
    elif pix.alpha:
        img_format = QImage.Format.Format_RGBA8888
    else:
        # Ensure 3-channel RGB without alpha
        if pix.n != 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        img_format = QImage.Format.Format_RGB888

    # Create QImage from buffer and explicitly call .copy() to decouple lifetime from C buffer
    qimg = QImage(
        pix.samples,
        pix.width,
        pix.height,
        pix.stride,
        img_format,
    ).copy()

    return qimg


def pixmap_to_qpixmap(pix: pymupdf.Pixmap) -> QPixmap:
    """Convert a PyMuPDF Pixmap to PySide6 QPixmap."""
    qimg = pixmap_to_qimage(pix)
    return QPixmap.fromImage(qimg)


class PDFRenderer:
    """High-performance renderer for PDF pages and thumbnails."""

    @staticmethod
    def render_page_to_pixmap(
        source: Union[PDFReader, pymupdf.Document],
        page_index: int,
        dpi: int = DEFAULT_RENDER_DPI,
    ) -> pymupdf.Pixmap:
        """Render a single page to a PyMuPDF Pixmap at specified DPI."""
        doc = source.doc if isinstance(source, PDFReader) else source
        if not (0 <= page_index < len(doc)):
            raise IndexError(f"Page index {page_index} out of range [0, {len(doc) - 1}]")

        page = doc[page_index]
        matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        return pix

    @classmethod
    def render_page_to_qpixmap(
        cls,
        source: Union[PDFReader, pymupdf.Document],
        page_index: int,
        dpi: int = DEFAULT_RENDER_DPI,
    ) -> QPixmap:
        """Render a page directly to QPixmap for PySide6 display."""
        pix = cls.render_page_to_pixmap(source, page_index, dpi=dpi)
        return pixmap_to_qpixmap(pix)

    @classmethod
    def render_page_to_image_file(
        cls,
        source: Union[PDFReader, pymupdf.Document],
        page_index: int,
        output_path: str | Path,
        dpi: int = DEFAULT_RENDER_DPI,
    ) -> Path:
        """Render a page and save to disk (e.g. PNG / JPEG for vision AI or cache)."""
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pix = cls.render_page_to_pixmap(source, page_index, dpi=dpi)
        pix.save(str(out_path))
        return out_path

    @classmethod
    def generate_thumbnail(
        cls,
        source: Union[PDFReader, pymupdf.Document],
        page_index: int,
        output_path: str | Path | None = None,
        max_size: int = 256,
    ) -> Path:
        """Generate a lightweight thumbnail for page listing or sidebar."""
        doc = source.doc if isinstance(source, PDFReader) else source
        page = doc[page_index]
        rect = page.rect
        scale = min(max_size / rect.width, max_size / rect.height)
        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        if output_path is None:
            THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
            output_path = THUMBNAILS_DIR / f"thumb_page_{page_index}_{int(scale * 100)}.png"

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out_path))
        return out_path
