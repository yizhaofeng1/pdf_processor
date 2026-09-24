"""Tests for question marker detection and false-positive filtering."""

from app.experimental.local_ai.types import OCRBlock
from app.experimental.local_detection.marker_detector import LocalMarkerDetector


def test_marker_detection_arabic_and_sections():
    """Verify Arabic numerals and Chinese section headers are correctly recognized."""
    detector = LocalMarkerDetector()
    blocks = [
        OCRBlock(text="一、选择题：1～8小题，每小题4分，共32分。", bbox=(0.05, 0.10, 0.90, 0.13), page_index=0),
        OCRBlock(text="1. 若极限存在，则常数 a 等于", bbox=(0.05, 0.15, 0.45, 0.18), page_index=0),
        OCRBlock(text="2、设函数 f(x) 连续，且", bbox=(0.05, 0.35, 0.45, 0.38), page_index=0),
        OCRBlock(text="17．(本题满分10分) 设曲线方程为", bbox=(0.05, 0.70, 0.90, 0.73), page_index=0),
    ]

    markers = detector.detect_markers(blocks, page_index=0)
    assert len(markers) == 4

    # Check section header
    sec = markers[0]
    assert sec.number == "一"
    assert sec.is_section_header is True

    # Check question markers
    q_nums = [m.number for m in markers if not m.is_section_header]
    assert q_nums == ["1", "2", "17"]


def test_marker_false_positive_filtering():
    """Verify dates, decimals, option letters, and isolated fractions are ignored."""
    detector = LocalMarkerDetector()
    blocks = [
        OCRBlock(text="2020年全国硕士研究生招生考试数学试卷", bbox=(0.10, 0.03, 0.90, 0.06), page_index=0),
        OCRBlock(text="A. 1/4. 且常数 c = 3.14", bbox=(0.05, 0.20, 0.40, 0.23), page_index=0),
        OCRBlock(text="B. -1/2", bbox=(0.05, 0.24, 0.40, 0.27), page_index=0),
        OCRBlock(text="4.", bbox=(0.80, 0.22, 0.85, 0.24), page_index=0),  # fraction denominator fragment on right
        OCRBlock(text="3. 下列积分收敛的是", bbox=(0.05, 0.40, 0.45, 0.43), page_index=0),
    ]

    markers = detector.detect_markers(blocks, page_index=0)
    assert len(markers) == 1
    assert markers[0].number == "3"
