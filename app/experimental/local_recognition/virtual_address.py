"""Virtual Address parsing, formatting, and validation logic.

Format: P{page}:R{row}:C{column}
Example: P03:R05:C02 or P3:R5:C2
"""

import re
from typing import Tuple, List


VA_REGEX = re.compile(r"^P(\d+):R(\d+):C(\d+)$", re.IGNORECASE)


class InvalidVirtualAddressError(ValueError):
    """Raised when a virtual address string is invalid or out of bounds."""
    pass


def format_virtual_address(page_index: int, row: int, col: int) -> str:
    """Format integer indices to standardized P{page:02d}:R{row:02d}:C{col:02d} address."""
    if page_index < 0 or row < 0 or col < 0:
        raise InvalidVirtualAddressError(f"Indices must be non-negative: ({page_index}, {row}, {col})")
    return f"P{page_index:02d}:R{row:02d}:C{col:02d}"


def parse_virtual_address(address_str: str) -> Tuple[int, int, int]:
    """Parse virtual address string into (page_index, row, col).

    Supports both zero-padded ('P03:R05:C02') and unpadded ('P3:R5:C2').
    """
    cleaned = address_str.strip().upper()
    match = VA_REGEX.match(cleaned)
    if not match:
        raise InvalidVirtualAddressError(f"Malformed virtual address string: '{address_str}'")

    page_index = int(match.group(1))
    row = int(match.group(2))
    col = int(match.group(3))

    return (page_index, row, col)


def validate_virtual_address(
    address_str: str,
    max_pages: int | None = None,
    max_rows: int | None = None,
    max_cols: int | None = None,
) -> bool:
    """Validate that address string is syntactically valid and within optional page/grid bounds."""
    try:
        p, r, c = parse_virtual_address(address_str)
    except InvalidVirtualAddressError:
        return False

    if max_pages is not None and (p < 0 or p >= max_pages):
        return False
    if max_rows is not None and (r < 0 or r >= max_rows):
        return False
    if max_cols is not None and (c < 0 or c >= max_cols):
        return False

    return True


def get_neighbor_addresses(
    address_str: str,
    max_rows: int,
    max_cols: int,
    radius: int = 1,
) -> List[str]:
    """Get all valid neighboring virtual addresses within a given Manhattan or Chebyshev radius."""
    p, r, c = parse_virtual_address(address_str)
    neighbors = []

    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            nr = r + dr
            nc = c + dc
            if 0 <= nr < max_rows and 0 <= nc < max_cols:
                neighbors.append(format_virtual_address(p, nr, nc))

    return sorted(list(set(neighbors)))
