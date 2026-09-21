"""Tiler: Rendering low-res whole-page images, high-DPI local candidate crops, and grid overlays."""

from pathlib import Path
from typing import Tuple, Union, Optional, List
import pymupdf
from PIL import Image, ImageDraw, ImageFont
import io

from ...pdf.reader import PDFReader
from ...pdf.coordinate import normalized_to_pdf_rect
from .page_table import VirtualPageTable
from .config import EXPERIMENT_CROPS_DIR


class Tiler:
    """Handles rendering and cropping for the VAQL pipeline."""

    @staticmethod
    def render_coarse_page(
        reader_or_doc: Union[PDFReader, pymupdf.Document],
        page_index: int,
        dpi: int = 150,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Render a full page at coarse resolution (default 150 DPI) for coarse address detection."""
        doc = reader_or_doc.doc if isinstance(reader_or_doc, PDFReader) else reader_or_doc
        page = doc[page_index]

        matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        if output_path is None:
            EXPERIMENT_CROPS_DIR.mkdir(parents=True, exist_ok=True)
            output_path = EXPERIMENT_CROPS_DIR / f"page_{page_index}_coarse_{dpi}dpi.png"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        pix.save(str(output_path))
        return output_path

    @staticmethod
    def crop_candidate_high_res(
        reader_or_doc: Union[PDFReader, pymupdf.Document],
        page_index: int,
        normalized_rect: Tuple[float, float, float, float],
        dpi: int = 250,
        max_pixels: int = 1800000,
        output_path: Optional[Union[str, Path]] = None,
        padding_ratio: Tuple[float, float] = (0.01, 0.01),
    ) -> Path:
        """Render a high-resolution crop directly from the vector PDF (PyMuPDF clip).

        Ensures crisp, readable text for small VLM local refinement while enforcing
        max_pixels to prevent token context explosion.
        """
        doc = reader_or_doc.doc if isinstance(reader_or_doc, PDFReader) else reader_or_doc
        page = doc[page_index]

        # Convert normalized rect to PDF point rect with safety padding
        pdf_clip = normalized_to_pdf_rect(page.rect, normalized_rect, padding_ratio=padding_ratio)

        # Dynamic DPI adjustment to prevent token overflow on large candidates
        effective_dpi = dpi
        est_w = int(pdf_clip.width * effective_dpi / 72.0)
        est_h = int(pdf_clip.height * effective_dpi / 72.0)
        est_pixels = est_w * est_h

        if est_pixels > max_pixels:
            scale = (max_pixels / est_pixels) ** 0.5
            effective_dpi = max(100, int(dpi * scale))

        matrix = pymupdf.Matrix(effective_dpi / 72.0, effective_dpi / 72.0)
        pix = page.get_pixmap(matrix=matrix, clip=pdf_clip, alpha=False)

        if output_path is None:
            EXPERIMENT_CROPS_DIR.mkdir(parents=True, exist_ok=True)
            nx1, ny1, nx2, ny2 = normalized_rect
            output_path = EXPERIMENT_CROPS_DIR / f"crop_p{page_index}_{int(nx1*100)}_{int(ny1*100)}_{effective_dpi}dpi.png"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        pix.save(str(output_path))
        return output_path

    @staticmethod
    def add_grid_overlay(
        image_path: Union[str, Path],
        page_table: VirtualPageTable,
        output_path: Optional[Union[str, Path]] = None,
        highlight_regions: Optional[List[str]] = None,
        line_color: str = "#EF4444",
        highlight_color: str = "#10B981",
        line_width: int = 2,
    ) -> Path:
        """Draw virtual address grid lines and prominent address badges onto an image copy.

        Used for UI visualization and vision-model spatial grounding in VAQL mode.
        """
        img_path = Path(image_path)
        img = Image.open(img_path).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        w, h = img.size
        highlight_set = set(highlight_regions or [])

        # Choose a readable font size for the grid resolution
        font_size = max(14, int(min(w, h) * 0.016))
        font = None
        for font_name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "Arial-Bold.ttf", "arial.ttf"):
            try:
                font = ImageFont.truetype(font_name, font_size)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()

        for region in page_table.get_all_regions():
            nx1, ny1, nx2, ny2 = region.normalized_rect
            px1 = int(nx1 * w)
            py1 = int(ny1 * h)
            px2 = int(nx2 * w)
            py2 = int(ny2 * h)

            is_highlighted = region.address in highlight_set

            if is_highlighted:
                # Translucent green fill
                draw.rectangle([px1, py1, px2, py2], fill=(16, 185, 129, 70), outline=(16, 185, 129, 240), width=line_width + 1)
            else:
                draw.rectangle([px1, py1, px2, py2], outline=(239, 68, 68, 160), width=line_width)

            # Draw a prominent high-contrast badge for the label so the VLM can read it clearly
            tag = f"R{region.row:02d}C{region.col:02d}"
            tx = px1 + 4
            ty = py1 + 4

            try:
                t_bbox = draw.textbbox((tx, ty), tag, font=font)
                pad = 3
                badge_box = [t_bbox[0] - pad, t_bbox[1] - pad, t_bbox[2] + pad, t_bbox[3] + pad]
                badge_bg = (16, 185, 129, 230) if is_highlighted else (254, 242, 242, 230)
                badge_border = (5, 150, 105, 255) if is_highlighted else (239, 68, 68, 255)
                draw.rectangle(badge_box, fill=badge_bg, outline=badge_border, width=1)
            except Exception:
                pass

            text_color = (255, 255, 255, 255) if is_highlighted else (185, 28, 28, 255)
            draw.text((tx, ty), tag, fill=text_color, font=font)

        combined = Image.alpha_composite(img, overlay).convert("RGB")

        if output_path is None:
            output_path = img_path.parent / f"{img_path.stem}_grid{img_path.suffix}"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        combined.save(str(output_path))
        return output_path
