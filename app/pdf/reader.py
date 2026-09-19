"""PDF Loader, validation and structural analysis module."""

from pathlib import Path
import hashlib
from typing import Any
import pymupdf
from pydantic import BaseModel, Field

from ..models.page import PageInfo, PageType


class PDFValidationResult(BaseModel):
    """Result of PDF pre-flight validation."""
    is_valid: bool
    error_message: str | None = None
    page_count: int = 0
    is_encrypted: bool = False
    file_size_bytes: int = 0


def compute_file_hash(file_path: str | Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file for caching and integrity tracking."""
    hasher = hashlib.sha256()
    path = Path(file_path)
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_pdf(file_path: str | Path) -> PDFValidationResult:
    """Validate that the given file path exists, is a valid PDF and is readable."""
    path = Path(file_path)
    if not path.exists():
        return PDFValidationResult(
            is_valid=False,
            error_message=f"文件不存在: {file_path}",
        )
    if not path.is_file():
        return PDFValidationResult(
            is_valid=False,
            error_message=f"路径不是普通文件: {file_path}",
        )
    if path.suffix.lower() != ".pdf":
        return PDFValidationResult(
            is_valid=False,
            error_message=f"文件扩展名非 .pdf: {path.suffix}",
        )

    file_size = path.stat().st_size
    if file_size == 0:
        return PDFValidationResult(
            is_valid=False,
            error_message="PDF 文件大小为 0 字节，文件已损坏。",
            file_size_bytes=0,
        )

    try:
        doc = pymupdf.open(str(path))
    except Exception as e:
        return PDFValidationResult(
            is_valid=False,
            error_message=f"无法打开 PDF 文件: {e}",
            file_size_bytes=file_size,
        )

    try:
        is_encrypted = doc.is_encrypted
        if is_encrypted and not doc.authenticate(""):
            return PDFValidationResult(
                is_valid=False,
                error_message="PDF 文件已加密且需要密码访问。",
                page_count=len(doc),
                is_encrypted=True,
                file_size_bytes=file_size,
            )

        page_count = len(doc)
        if page_count == 0:
            return PDFValidationResult(
                is_valid=False,
                error_message="PDF 文件不包含任何有效页面。",
                page_count=0,
                file_size_bytes=file_size,
            )

        return PDFValidationResult(
            is_valid=True,
            page_count=page_count,
            is_encrypted=is_encrypted,
            file_size_bytes=file_size,
        )
    finally:
        doc.close()


class PDFReader:
    """Encapsulates read operations and metadata extraction on a source PDF."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path).resolve()
        validation = validate_pdf(self.file_path)
        if not validation.is_valid:
            raise ValueError(validation.error_message or "无效的 PDF 文件")

        self.doc: pymupdf.Document = pymupdf.open(str(self.file_path))
        self.file_hash = compute_file_hash(self.file_path)
        self._page_count = len(self.doc)

    @property
    def pdf_path(self) -> Path:
        """Alias for file_path for convenience and backwards compatibility."""
        return self.file_path

    @property
    def page_count(self) -> int:
        return self._page_count

    @property
    def document(self) -> pymupdf.Document:
        """Alias for doc to avoid AttributeError."""
        return self.doc

    def get_page(self, page_index: int) -> pymupdf.Page:
        """Return PyMuPDF Page object for given 0-indexed page."""
        if not (0 <= page_index < self._page_count):
            raise IndexError(f"Page index {page_index} out of range [0, {self._page_count - 1}]")
        return self.doc[page_index]

    def get_page_rect(self, page_index: int) -> tuple[float, float, float, float]:
        """Return (x0, y0, x1, y1) in PDF points."""
        page = self.get_page(page_index)
        rect = page.rect
        return (rect.x0, rect.y0, rect.x1, rect.y1)

    def detect_page_type(self, page_index: int) -> PageType:
        """Determine if page is native text, scanned image, or mixed."""
        page = self.get_page(page_index)
        text = page.get_text().strip()
        images = page.get_images()

        has_text = len(text) > 50
        has_images = len(images) > 0

        if has_text and not has_images:
            return PageType.TEXT_PDF
        elif not has_text and has_images:
            return PageType.IMAGE_PDF
        return PageType.MIXED_PDF

    def get_page_info(self, page_index: int, project_id: str = "") -> PageInfo:
        """Return structured PageInfo domain model."""
        page = self.get_page(page_index)
        page_type = self.detect_page_type(page_index)
        return PageInfo(
            project_id=project_id,
            page_index=page_index,
            width=page.rect.width,
            height=page.rect.height,
            rotation=page.rotation,
            page_type=page_type,
        )

    def extract_text_blocks(self, page_index: int) -> list[dict[str, Any]]:
        """Extract native text blocks and bounding boxes (if available)."""
        page = self.get_page(page_index)
        data = page.get_text("dict")
        blocks = []
        for block in data.get("blocks", []):
            if block.get("type") == 0:  # Text block
                lines_text = []
                for line in block.get("lines", []):
                    line_spans = [span.get("text", "") for span in line.get("spans", [])]
                    lines_text.append("".join(line_spans))
                blocks.append({
                    "bbox": block.get("bbox"),
                    "text": "\n".join(lines_text),
                    "lines_count": len(block.get("lines", [])),
                })
        return blocks

    def close(self) -> None:
        if self.doc and not self.doc.is_closed:
            self.doc.close()

    def __enter__(self) -> "PDFReader":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
