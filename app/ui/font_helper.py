"""Font configuration helper for cross-platform CJK/Chinese text rendering."""

import os
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase

logger = logging.getLogger("examsplit.fonts")

PREFERRED_FAMILIES = [
    "Microsoft YaHei",
    "Microsoft YaHei UI",
    "Noto Sans SC",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "WenQuanYi Micro Hei",
    "SimHei",
    "PingFang SC",
    "Segoe UI",
    "sans-serif",
]

CANDIDATE_FONT_PATHS = [
    # WSL2 mounted Windows fonts
    Path("/mnt/c/Windows/Fonts/msyh.ttc"),
    Path("/mnt/c/Windows/Fonts/msyh.ttf"),
    Path("/mnt/c/Windows/Fonts/NotoSansSC-VF.ttf"),
    Path("/mnt/c/Windows/Fonts/simhei.ttf"),
    Path("/mnt/c/Windows/Fonts/simsun.ttc"),
    # Standard Linux CJK font paths
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
]


def setup_application_fonts(app: QApplication) -> None:
    """Ensure Chinese glyphs render clearly without square tofu boxes in WSL2/Linux."""
    # 1. Try to load external font files if needed
    for font_path in CANDIDATE_FONT_PATHS:
        if font_path.exists():
            try:
                font_id = QFontDatabase.addApplicationFont(str(font_path))
                if font_id >= 0:
                    loaded_families = QFontDatabase.applicationFontFamilies(font_id)
                    logger.debug(f"Loaded font from {font_path}: {loaded_families}")
            except Exception as e:
                logger.debug(f"Failed to load font from {font_path}: {e}")

    # 2. Pick the best available family from preferred list
    available_families = set(QFontDatabase.families())
    selected_family = "sans-serif"
    for fam in PREFERRED_FAMILIES:
        if fam in available_families:
            selected_family = fam
            break

    logger.info(f"Setting primary application UI font to: {selected_family}")

    # 3. Configure default application font (comfortable 13pt for Chinese glyphs)
    app_font = QFont(selected_family, 13)
    app_font.setFamilies(PREFERRED_FAMILIES)
    app.setFont(app_font)


def get_ui_font(size: int = 13, bold: bool = False) -> QFont:
    """Return a styled QFont respecting CJK fallbacks."""
    font = QApplication.font()
    font.setPointSize(size)
    if bold:
        font.setBold(True)
    return font
