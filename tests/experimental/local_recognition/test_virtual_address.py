"""Unit tests for Virtual Address parsing, formatting, and validation."""

import pytest
from app.experimental.local_recognition.virtual_address import (
    parse_virtual_address,
    format_virtual_address,
    validate_virtual_address,
    get_neighbor_addresses,
    InvalidVirtualAddressError,
)


def test_format_virtual_address():
    assert format_virtual_address(0, 0, 0) == "P00:R00:C00"
    assert format_virtual_address(3, 5, 2) == "P03:R05:C02"
    assert format_virtual_address(12, 7, 3) == "P12:R07:C03"

    with pytest.raises(InvalidVirtualAddressError):
        format_virtual_address(-1, 0, 0)
    with pytest.raises(InvalidVirtualAddressError):
        format_virtual_address(0, -1, 0)


def test_parse_virtual_address_padded_and_unpadded():
    # Padded
    assert parse_virtual_address("P03:R05:C02") == (3, 5, 2)
    assert parse_virtual_address("p00:r00:c00") == (0, 0, 0)

    # Unpadded
    assert parse_virtual_address("P3:R5:C2") == (3, 5, 2)
    assert parse_virtual_address("P0:R0:C0") == (0, 0, 0)

    # Invalid formats
    with pytest.raises(InvalidVirtualAddressError):
        parse_virtual_address("R05:C02")
    with pytest.raises(InvalidVirtualAddressError):
        parse_virtual_address("P03-R05-C02")
    with pytest.raises(InvalidVirtualAddressError):
        parse_virtual_address("P-1:R2:C3")
    with pytest.raises(InvalidVirtualAddressError):
        parse_virtual_address("invalid")


def test_validate_virtual_address():
    assert validate_virtual_address("P03:R05:C02", max_pages=10, max_rows=8, max_cols=4) is True
    # Row out of bounds
    assert validate_virtual_address("P03:R09:C02", max_pages=10, max_rows=8, max_cols=4) is False
    # Column out of bounds
    assert validate_virtual_address("P03:R05:C05", max_pages=10, max_rows=8, max_cols=4) is False
    # Page out of bounds
    assert validate_virtual_address("P15:R05:C02", max_pages=10, max_rows=8, max_cols=4) is False
    # Invalid syntax
    assert validate_virtual_address("P03_R05_C02") is False


def test_get_neighbor_addresses():
    # Center cell in 8x4 grid
    neighbors = get_neighbor_addresses("P00:R04:C02", max_rows=8, max_cols=4, radius=1)
    assert len(neighbors) == 9
    assert "P00:R04:C02" in neighbors
    assert "P00:R03:C01" in neighbors
    assert "P00:R05:C03" in neighbors

    # Top-left corner cell (should be clipped by boundary to 4 cells)
    corner_neighbors = get_neighbor_addresses("P00:R00:C00", max_rows=8, max_cols=4, radius=1)
    assert len(corner_neighbors) == 4
    assert sorted(corner_neighbors) == ["P00:R00:C00", "P00:R00:C01", "P00:R01:C00", "P00:R01:C01"]

    # Radius 0 (only itself)
    self_neighbors = get_neighbor_addresses("P00:R04:C02", max_rows=8, max_cols=4, radius=0)
    assert self_neighbors == ["P00:R04:C02"]
