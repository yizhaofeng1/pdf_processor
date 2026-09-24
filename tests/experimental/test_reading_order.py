"""Tests for reading order determination and column structure analysis."""

from app.experimental.local_ai.types import OCRBlock
from app.experimental.local_detection.reading_order import ReadingOrderDetector, sort_elements_reading_order


def test_single_column_reading_order():
    """Verify single-column elements are sorted top-to-bottom."""
    blocks = [
        OCRBlock(text="Line 3", bbox=(0.05, 0.40, 0.90, 0.45), page_index=0),
        OCRBlock(text="Line 1", bbox=(0.05, 0.10, 0.90, 0.15), page_index=0),
        OCRBlock(text="Line 2", bbox=(0.05, 0.25, 0.90, 0.30), page_index=0),
    ]
    sorted_b = sort_elements_reading_order(blocks)
    assert [b.text for b in sorted_b] == ["Line 1", "Line 2", "Line 3"]


def test_two_column_detection_and_ordering():
    """Verify two-column layout detection and left-column then right-column sorting."""
    detector = ReadingOrderDetector()

    # Create distinct left and right column elements
    left_blocks = [
        OCRBlock(text="Left 1", bbox=(0.05, 0.15, 0.45, 0.20), page_index=0),
        OCRBlock(text="Left 2", bbox=(0.05, 0.30, 0.45, 0.35), page_index=0),
        OCRBlock(text="Left 3", bbox=(0.05, 0.50, 0.45, 0.55), page_index=0),
        OCRBlock(text="Left 4", bbox=(0.05, 0.70, 0.45, 0.75), page_index=0),
    ]
    right_blocks = [
        OCRBlock(text="Right 1", bbox=(0.55, 0.15, 0.95, 0.20), page_index=0),
        OCRBlock(text="Right 2", bbox=(0.55, 0.30, 0.95, 0.35), page_index=0),
        OCRBlock(text="Right 3", bbox=(0.55, 0.50, 0.95, 0.55), page_index=0),
        OCRBlock(text="Right 4", bbox=(0.55, 0.70, 0.95, 0.75), page_index=0),
    ]
    header = OCRBlock(text="Header", bbox=(0.10, 0.02, 0.90, 0.06), page_index=0)
    footer = OCRBlock(text="Footer", bbox=(0.40, 0.95, 0.60, 0.98), page_index=0)

    all_blocks = [footer, right_blocks[2], left_blocks[1], header, right_blocks[0], left_blocks[0], left_blocks[3], right_blocks[1], left_blocks[2], right_blocks[3]]

    is_two_col, split = detector.detect_two_column(all_blocks)
    assert is_two_col is True
    assert split == 0.50

    sorted_b = detector.sort_in_reading_order(all_blocks)
    texts = [b.text for b in sorted_b]

    # Header must be first, all left elements, all right elements, footer last
    assert texts[0] == "Header"
    assert texts[1:5] == ["Left 1", "Left 2", "Left 3", "Left 4"]
    assert texts[5:9] == ["Right 1", "Right 2", "Right 3", "Right 4"]
    assert texts[9] == "Footer"
