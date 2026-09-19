"""Design System and Modern Cyber-Slate Tech Stylesheet for ExamSplit AI.

Implements high-end Sci-Fi / Cyber-Tech aesthetics:
- Obsidian / Deep Space Slate harmonious dark color palette (#090D16, #0F172A, #1E293B).
- Luminous Electric Cyan (#38BDF8) & Tech Blue (#2563EB) accents.
- Eye-comfort enlarged typography (14px-16px base body, 18px-24px headers).
- Crisp high-contrast readability, glowing focus states, and sleek tech scrollbars.
"""

MODERN_APP_STYLESHEET = """
/* Global Application Reset & Typography */
QWidget {
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", "Noto Sans SC", -apple-system, sans-serif;
    font-size: 15.5px;
    color: #F1F5F9;
    background-color: transparent;
    outline: none;
}

QMainWindow {
    background-color: #090D16;
}

QDialog {
    background-color: #0F172A;
    color: #F1F5F9;
}

/* ToolBar Styling */
QToolBar {
    background-color: #0B0F19;
    border-bottom: 1px solid #1E293B;
    padding: 10px 16px;
    spacing: 12px;
}

QToolButton {
    background-color: #131C2E;
    color: #E2E8F0;
    font-weight: 600;
    font-size: 15px;
    padding: 9px 18px;
    min-height: 40px;
    border-radius: 8px;
    border: 1px solid #1E293B;
}

QToolButton:hover {
    background-color: #1E293B;
    border-color: #38BDF8;
    color: #38BDF8;
}

QToolButton:pressed {
    background-color: #0F172A;
}

QToolButton:disabled {
    color: #475569;
    background-color: #0B0F19;
    border-color: #1E293B;
}

/* PushButtons */
QPushButton {
    background-color: #1E293B;
    color: #F1F5F9;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 9px 20px;
    min-height: 40px;
    font-size: 15px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #283548;
    border-color: #38BDF8;
    color: #FFFFFF;
}

QPushButton:pressed {
    background-color: #0F172A;
    border-color: #0284C7;
}

QPushButton:disabled {
    background-color: #131C2E;
    color: #475569;
    border-color: #1E293B;
}

/* Primary Action Buttons (Cyber Cyan-Blue Gradient) */
QPushButton[primary="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #2563EB);
    color: #FFFFFF;
    border: 1px solid #38BDF8;
    font-weight: 700;
    font-size: 15.5px;
    min-height: 42px;
    padding: 10px 24px;
}

QPushButton[primary="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369A1, stop:1 #1D4ED8);
    border-color: #7DD3FC;
}

QPushButton[primary="true"]:pressed {
    background-color: #1E40AF;
}

/* Success Buttons (Matrix Mint) */
QPushButton[success="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10B981);
    color: #FFFFFF;
    border: 1px solid #34D399;
    font-weight: 700;
    font-size: 15px;
    min-height: 40px;
    padding: 9px 20px;
}

QPushButton[success="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
    border-color: #6EE7B7;
}

/* Danger Buttons (Warning Coral) */
QPushButton[danger="true"] {
    background-color: #7F1D1D;
    color: #FEE2E2;
    border: 1px solid #EF4444;
    font-weight: 600;
    font-size: 15px;
    min-height: 40px;
    padding: 9px 20px;
}

QPushButton[danger="true"]:hover {
    background-color: #991B1B;
    border-color: #F87171;
    color: #FFFFFF;
}

QPushButton[success="true"]:disabled,
QPushButton[danger="true"]:disabled,
QPushButton[primary="true"]:disabled {
    background-color: #131C2E;
    color: #475569;
    border: 1px solid #1E293B;
}

/* Inputs & Form Controls */
QLineEdit, QSpinBox {
    background-color: #0B1120;
    color: #F8FAFC;
    border: 1.5px solid #334155;
    border-radius: 8px;
    padding: 6px 12px;
    min-height: 36px;
    font-size: 15px;
    selection-background-color: #0284C7;
    selection-color: #FFFFFF;
}

QComboBox {
    background-color: #0B1120;
    color: #F8FAFC;
    border: 1.5px solid #334155;
    border-radius: 8px;
    padding: 4px 34px 4px 12px;
    min-height: 36px;
    font-size: 14.5px;
    selection-background-color: #0284C7;
    selection-color: #FFFFFF;
}

QComboBox:hover {
    border-color: #38BDF8;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1.5px solid #38BDF8;
    background-color: #0F172A;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border-left: 1px solid #334155;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    background-color: #1E293B;
}

QComboBox::down-arrow {
    width: 0px;
    height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #38BDF8;
    margin-right: 2px;
}

QComboBox::down-arrow:hover {
    border-top: 6px solid #7DD3FC;
}

QComboBox QAbstractItemView {
    background-color: #0F172A;
    border: 1.5px solid #38BDF8;
    border-radius: 8px;
    padding: 6px;
    font-size: 14.5px;
    color: #F1F5F9;
    selection-background-color: #1E293B;
    selection-color: #38BDF8;
}

/* Context Menus & Popups */
QMenu {
    background-color: #0F172A;
    border: 1.5px solid #38BDF8;
    border-radius: 8px;
    padding: 6px;
    color: #F1F5F9;
}

QMenu::item {
    background-color: transparent;
    color: #F1F5F9;
    padding: 8px 24px;
    border-radius: 6px;
    font-size: 14.5px;
    font-weight: 500;
}

QMenu::item:selected {
    background-color: #1E293B;
    color: #38BDF8;
    font-weight: 700;
}

QMenu::item:disabled {
    color: #64748B;
}

QMenu::separator {
    height: 1px;
    background: #334155;
    margin: 4px 8px;
}

/* Lists & Trees */
QListWidget {
    background-color: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 10px;
    padding: 8px;
    color: #E2E8F0;
}

QListWidget::item {
    border-radius: 6px;
    padding: 10px 14px;
    min-height: 40px;
    margin: 3px 0;
    color: #E2E8F0;
    font-size: 15px;
}

QListWidget::item:hover {
    background-color: #1E293B;
    color: #38BDF8;
}

QListWidget::item:selected {
    background-color: #172554;
    color: #38BDF8;
    font-weight: 700;
    border: 1.5px solid #38BDF8;
}

/* CheckBox Styling */
QCheckBox {
    spacing: 12px;
    color: #E2E8F0;
    font-size: 15px;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 1.5px solid #475569;
    border-radius: 5px;
    background-color: #0B1120;
}

QCheckBox::indicator:hover {
    border-color: #38BDF8;
}

QCheckBox::indicator:checked {
    background-color: #0284C7;
    border-color: #38BDF8;
}

/* RadioButton Styling */
QRadioButton {
    spacing: 12px;
    color: #E2E8F0;
    font-size: 15px;
}

QRadioButton::indicator {
    width: 20px;
    height: 20px;
    border: 1.5px solid #475569;
    border-radius: 10px;
    background-color: #0B1120;
}

QRadioButton::indicator:hover {
    border-color: #38BDF8;
}

QRadioButton::indicator:checked {
    background-color: #0284C7;
    border-color: #38BDF8;
}

/* GroupBox Card */
QGroupBox {
    background-color: #111827;
    border: 1px solid #1E293B;
    border-radius: 10px;
    margin-top: 24px;
    padding: 20px 16px 16px 16px;
    font-weight: 700;
    font-size: 16px;
    color: #F8FAFC;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 12px;
    left: 14px;
    color: #38BDF8;
    font-size: 16px;
    font-weight: 700;
}

/* Status Bar */
QStatusBar {
    background-color: #0B0F19;
    border-top: 1px solid #1E293B;
    color: #94A3B8;
    font-size: 14px;
    padding: 6px 16px;
}

/* Modern Sci-Fi Thin Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #090D16;
    width: 10px;
    border-radius: 5px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 28px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #38BDF8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #090D16;
    height: 10px;
    border-radius: 5px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #334155;
    min-width: 28px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #38BDF8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Splitter handle */
QSplitter::handle {
    background-color: #1E293B;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}

QSplitter::handle:hover {
    background-color: #38BDF8;
}

/* Menu Bar & Menus */
QMenuBar {
    background-color: #0B0F19;
    border-bottom: 1px solid #1E293B;
    color: #E2E8F0;
    font-size: 15px;
    padding: 5px;
}

QMenuBar::item {
    padding: 7px 14px;
    border-radius: 6px;
}

QMenuBar::item:selected {
    background-color: #1E293B;
    color: #38BDF8;
}

QMenu {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px;
    color: #F1F5F9;
    font-size: 15px;
}

QMenu::item {
    padding: 9px 26px;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: #1E293B;
    color: #38BDF8;
}

QMenu::separator {
    height: 1px;
    background: #1E293B;
    margin: 4px 8px;
}
"""


def get_badge_style(color_hex: str, bg_hex: str) -> str:
    """Return styling for modern tag badge pills."""
    return f"""
        QLabel {{
            color: {color_hex};
            background-color: {bg_hex};
            border-radius: 12px;
            padding: 3px 10px;
            font-size: 12.5px;
            font-weight: 700;
        }}
    """
