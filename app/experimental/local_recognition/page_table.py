"""Virtual Page Table: Deterministic mapping between Virtual Addresses, Normalized Rects, and PDF Coordinates."""

from typing import Dict, List, Tuple, Union
import pymupdf

from .types import VirtualRegion
from .virtual_address import parse_virtual_address, format_virtual_address, InvalidVirtualAddressError


class VirtualPageTable:
    """Page Table for resolving discrete virtual addresses into continuous physical/normalized geometry."""

    def __init__(
        self,
        page_index: int,
        page_rect: Union[pymupdf.Rect, Tuple[float, float, float, float]],
        rows: int = 8,
        columns: int = 4,
    ) -> None:
        if rows <= 0 or columns <= 0:
            raise ValueError(f"Rows ({rows}) and columns ({columns}) must be positive integers.")

        self.page_index = page_index
        if isinstance(page_rect, pymupdf.Rect):
            self.x0 = page_rect.x0
            self.y0 = page_rect.y0
            self.width = page_rect.width
            self.height = page_rect.height
        else:
            x0, y0, x1, y1 = page_rect
            self.x0 = min(x0, x1)
            self.y0 = min(y0, y1)
            self.width = abs(x1 - x0)
            self.height = abs(y1 - y0)

        self.rows = rows
        self.columns = columns
        self._table: Dict[str, VirtualRegion] = {}
        self._build_table()

    def _build_table(self) -> None:
        """Construct the discrete virtual region grid for this page."""
        cell_w_norm = 1.0 / self.columns
        cell_h_norm = 1.0 / self.rows

        for r in range(self.rows):
            for c in range(self.columns):
                addr = format_virtual_address(self.page_index, r, c)

                # Normalized coordinates in [0.0, 1.0]
                nx1 = c * cell_w_norm
                ny1 = r * cell_h_norm
                nx2 = (c + 1) * cell_w_norm
                ny2 = (r + 1) * cell_h_norm

                # Physical PDF point coordinates
                px0 = self.x0 + nx1 * self.width
                py0 = self.y0 + ny1 * self.height
                px1 = self.x0 + nx2 * self.width
                py1 = self.y0 + ny2 * self.height

                region = VirtualRegion(
                    page_index=self.page_index,
                    row=r,
                    col=c,
                    address=addr,
                    normalized_rect=(round(nx1, 6), round(ny1, 6), round(nx2, 6), round(ny2, 6)),
                    pdf_rect=(round(px0, 2), round(py0, 2), round(px1, 2), round(py1, 2)),
                )
                self._table[addr] = region

    def resolve(self, address_str: str) -> VirtualRegion:
        """Resolve a single virtual address to its corresponding VirtualRegion.

        Raises:
            InvalidVirtualAddressError: If address format is invalid or references another page / out of bounds.
        """
        p, r, c = parse_virtual_address(address_str)
        if p != self.page_index:
            raise InvalidVirtualAddressError(
                f"Address '{address_str}' page index {p} does not match PageTable page {self.page_index}"
            )
        if not (0 <= r < self.rows and 0 <= c < self.columns):
            raise InvalidVirtualAddressError(
                f"Address '{address_str}' out of bounds for grid {self.rows}x{self.columns}"
            )

        standard_addr = format_virtual_address(p, r, c)
        return self._table[standard_addr]

    def resolve_multiple(self, addresses: List[str]) -> List[VirtualRegion]:
        """Resolve multiple virtual addresses, skipping any invalid ones with warning."""
        results = []
        for addr in addresses:
            try:
                results.append(self.resolve(addr))
            except Exception:
                continue
        return results

    def get_all_regions(self) -> List[VirtualRegion]:
        """Return all regions defined in this page table in row-major order."""
        return list(self._table.values())

    def get_region_at_normalized_point(self, nx: float, ny: float) -> VirtualRegion:
        """Find the virtual region containing the given normalized point (nx, ny)."""
        nx = max(0.0, min(0.999999, nx))
        ny = max(0.0, min(0.999999, ny))

        c = int(nx * self.columns)
        r = int(ny * self.rows)
        return self.resolve(format_virtual_address(self.page_index, r, c))
