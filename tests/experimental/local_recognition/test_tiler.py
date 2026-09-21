"""Unit tests for Tiler rendering, cropping, and grid overlays."""

import pymupdf
from pathlib import Path
from app.experimental.local_recognition.tiler import Tiler
from app.experimental.local_recognition.page_table import VirtualPageTable


def test_tiler_rendering_and_crop(tmp_path):
    # Create an in-memory PDF with 1 page
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(pymupdf.Rect(50, 50, 200, 200), color=(1, 0, 0), fill=(1, 0.8, 0.8))

    # 1. Coarse render
    coarse_path = tmp_path / "coarse.png"
    out = Tiler.render_coarse_page(doc, 0, dpi=100, output_path=coarse_path)
    assert out.exists()
    assert out.stat().st_size > 0

    # 2. Candidate high-res crop
    crop_path = tmp_path / "crop.png"
    crop_out = Tiler.crop_candidate_high_res(
        doc,
        page_index=0,
        normalized_rect=(0.1, 0.1, 0.4, 0.4),
        dpi=200,
        output_path=crop_path,
    )
    assert crop_out.exists()
    assert crop_out.stat().st_size > 0

    # 3. Grid overlay
    table = VirtualPageTable(0, (0, 0, 595, 842), rows=8, columns=4)
    overlay_path = tmp_path / "overlay.png"
    overlay_out = Tiler.add_grid_overlay(
        coarse_path,
        table,
        output_path=overlay_path,
        highlight_regions=["P00:R00:C00"],
    )
    assert overlay_out.exists()
    assert overlay_out.stat().st_size > 0

    doc.close()
