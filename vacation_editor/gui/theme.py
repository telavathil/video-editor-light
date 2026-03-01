from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Design tokens — sourced from design/video-editor-light.pen variables
# ---------------------------------------------------------------------------

BG_PRIMARY = "#1C1C1E"
BG_PANEL = "#252528"
BG_ELEVATED = "#2C2C2F"
BG_INPUT = "#3A3A3D"

BORDER = "#38383B"

TEXT_PRIMARY = "#F2F2F7"
TEXT_SECONDARY = "#8E8E93"
TEXT_MUTED = "#48484A"

ACCENT_BLUE = "#0A84FF"
ACCENT_GREEN = "#30D158"
ACCENT_ORANGE = "#FF9F0A"
ACCENT_RED = "#FF453A"

# Section palette: (fill rgba, border) — cycles by index
SECTION_PALETTE: list[tuple[str, str]] = [
    ("#0A84FF44", "#0A84FF"),
    ("#FF9F0A33", "#FF9F0A"),
    ("#30D15833", "#30D158"),
    ("#FF453A33", "#FF453A"),
]


def section_colors(index: int) -> tuple[str, str]:
    """Return (fill_hex, border_hex) for a section at the given index."""
    return SECTION_PALETTE[index % len(SECTION_PALETTE)]


# ---------------------------------------------------------------------------
# Application-wide Qt stylesheet
# ---------------------------------------------------------------------------

STYLESHEET = f"""
QWidget {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: -apple-system, BlinkMacSystemFont, "Inter", sans-serif;
    font-size: 12px;
    border: none;
    outline: none;
}}

QMainWindow, QDialog {{
    background-color: {BG_PRIMARY};
}}

/* Scroll bars */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BG_INPUT};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
}}
QScrollBar::handle:horizontal {{
    background: {BG_INPUT};
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* Tooltips */
QToolTip {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* Menu bar */
QMenuBar {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px 8px;
}}
QMenuBar::item {{ padding: 4px 10px; border-radius: 4px; }}
QMenuBar::item:selected {{ background-color: {BG_INPUT}; }}
QMenu {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {ACCENT_BLUE}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 0; }}

/* Line edit */
QLineEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: {ACCENT_BLUE};
}}
QLineEdit:focus {{ border-color: {ACCENT_BLUE}; }}

/* Combo box */
QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 28px 4px 8px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_BLUE};
    outline: none;
}}

/* Splitter */
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(STYLESHEET)
