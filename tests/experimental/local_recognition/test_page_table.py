"""Unit tests for Virtual Page Table mapping and geometry resolution."""

import pytest
import pymupdf
from app.experimental.local_recognition.page_table import VirtualPageTable
from app.experimental.local_recognition.virtual_address import InvalidVirtualAddressError


def test_page_table_8x4_grid_a4():
    # A4 dimensions in points: 595.0 x 842.0
    page_rect = (0.0, 0.0, 595.0, 842.0)
    table = VirtualPageTable(page_index=0, page_rect=page_rect, rows=8, columns=4)

    regions = table.get_all_regions()
    assert len(regions) == 32

    # Top-left cell: R0C0
    r0c0 = table.resolve("P00:R00:C00")
    assert r0c0.row == 0
    assert r0c0.col == 0
    assert r0c0.normalized_rect == (0.0, 0.0, 0.25, 0.125)
    assert r0c0.pdf_rect == (0.0, 0.0, round(595.0 * 0.25, 2), round(842.0 * 0.125, 2))

    # Bottom-right cell: R7C3
    r7c3 = table.resolve("P00:R07:C03")
    assert r7c3.row == 7
    assert r7c3.col == 3
    assert r7c3.normalized_rect == (0.75, 0.875, 1.0, 1.0)
    assert r7c3.pdf_rect == (
        round(595.0 * 0.75, 2),
        round(842.0 * 0.875, 2),
        595.0,
        842.0,
    )


def test_page_table_landscape_and_arbitrary_dimensions():
    # Landscape page (842.0 x 595.0)
    table = VirtualPageTable(page_index=2, page_rect=(0.0, 0.0, 842.0, 595.0), rows=4, columns=2)
    regions = table.get_all_regions()
    assert len(regions) == 8

    r0c0 = table.resolve("P02:R00:C00")
    assert r0c0.normalized_rect == (0.0, 0.0, 0.5, 0.25)
    assert r0c0.pdf_rect == (0.0, 0.0, 421.0, round(595.0 * 0.25, 2))


def test_page_table_resolve_errors():
    table = VirtualPageTable(page_index=1, page_rect=(0.0, 0.0, 600.0, 800.0), rows=8, columns=4)

    # Wrong page index
    with pytest.raises(InvalidVirtualAddressError):
        table.resolve("P00:R00:C00")

    # Out of bounds row
    with pytest.raises(InvalidVirtualAddressError):
        table.resolve("P01:R08:C00")

    # Out of bounds col
    with pytest.raises(InvalidVirtualAddressError):
        table.resolve("P01:R00:C04")


def test_page_table_resolve_multiple():
    table = VirtualPageTable(page_index=0, page_rect=(0.0, 0.0, 600.0, 800.0), rows=8, columns=4)
    addrs = ["P00:R00:C00", "P00:R00:C01", "P99:R99:C99"]  # Last one is invalid
    res = table.resolve_multiple(addrs)
    assert len(res) == 2
    assert res[0].address == "P00:R00:C00"
    assert res[1].address == "P00:R00:C01"


def test_get_region_at_normalized_point():
    table = VirtualPageTable(page_index=0, page_rect=(0.0, 0.0, 600.0, 800.0), rows=8, columns=4)
    # Point at (0.1, 0.05) -> col 0, row 0
    reg = table.get_region_at_normalized_point(0.1, 0.05)
    assert reg.row == 0
    assert reg.col == 0

    # Point at (0.9, 0.95) -> col 3, row 7
    reg2 = table.get_region_at_normalized_point(0.9, 0.95)
    assert reg2.row == 7
    assert reg2.col == 3
