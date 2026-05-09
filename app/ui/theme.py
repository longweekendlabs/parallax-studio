from PySide6.QtGui import QColor

# Darkroom Motion Studio palette
C_WINDOW_BG       = "#0B1014"
C_PANEL_BG        = "#111820"
C_RAISED_PANEL    = "#17212B"
C_CANVAS_SURROUND = "#070A0D"
C_CHECKER_DARK    = "#1A222B"
C_CHECKER_LIGHT   = "#222C36"
C_ACCENT          = "#3DD9C9"
C_ACCENT_HOVER    = "#63F2E5"
C_EXPORT          = "#F2B35E"
C_DANGER          = "#E05D5D"
C_TEXT_MAIN       = "#E7EEF2"
C_TEXT_SECONDARY  = "#91A1AD"
C_TEXT_MUTED      = "#5F6F7B"
C_BORDER          = "#24313C"
C_BORDER_SOFT     = "#1B2731"

FONT_UI   = "Inter, SF Pro Display, SF Pro Text, system-ui, sans-serif"
FONT_MONO = "JetBrains Mono, SF Mono, Menlo, Consolas, monospace"

QSS = f"""
/* ── Global ── */
QWidget {{
    background-color: {C_WINDOW_BG};
    color: {C_TEXT_MAIN};
    font-family: Inter, "SF Pro Text", system-ui, sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}}

QMainWindow {{
    background-color: {C_WINDOW_BG};
}}

/* ── Scroll bars ── */
QScrollBar:vertical {{
    background: {C_PANEL_BG};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {C_BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background: {C_PANEL_BG};
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {C_BORDER};
    border-radius: 3px;
    min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Sliders ── */
QSlider::groove:horizontal {{
    height: 4px;
    background: #26313A;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {C_ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: #D8E4EA;
    border: 1px solid #BCD2DA;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: #FFFFFF;
}}

/* ── ComboBox ── */
QComboBox {{
    background-color: #0D141B;
    border: 1px solid {C_BORDER};
    border-radius: 7px;
    padding: 7px 12px;
    color: {C_TEXT_MAIN};
    font-size: 15px;
}}
QComboBox:hover {{
    border-color: {C_ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {C_TEXT_SECONDARY};
    width: 0;
    height: 0;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {C_RAISED_PANEL};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    color: {C_TEXT_MAIN};
    selection-background-color: {C_ACCENT}33;
    selection-color: {C_ACCENT};
    padding: 2px;
}}

/* ── Tool buttons / icon buttons ── */
QToolButton {{
    background: transparent;
    border: none;
    color: {C_TEXT_SECONDARY};
    border-radius: 4px;
    padding: 4px;
}}
QToolButton:hover {{
    background: {C_RAISED_PANEL};
    color: {C_TEXT_MAIN};
}}
QToolButton:pressed {{
    background: {C_BORDER};
}}

/* ── Push buttons ── */
QPushButton {{
    background-color: {C_RAISED_PANEL};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    color: {C_TEXT_MAIN};
    padding: 5px 14px;
    font-size: 13px;
}}
QPushButton:hover {{
    border-color: {C_ACCENT};
    color: {C_ACCENT};
}}
QPushButton:pressed {{
    background-color: {C_BORDER};
}}

QPushButton#exportBtn {{
    background-color: {C_EXPORT};
    border: none;
    color: #1A1000;
    font-weight: 600;
    padding: 5px 18px;
    border-radius: 6px;
}}
QPushButton#exportBtn:hover {{
    background-color: #FFCC80;
}}

QPushButton#accentBtn {{
    background-color: {C_ACCENT}22;
    border: 1px solid {C_ACCENT}66;
    color: {C_ACCENT};
}}
QPushButton#accentBtn:hover {{
    background-color: {C_ACCENT}44;
    border-color: {C_ACCENT};
}}

QPushButton#dangerBtn {{
    background-color: {C_DANGER}22;
    border: 1px solid {C_DANGER}66;
    color: {C_DANGER};
}}
QPushButton#dangerBtn:hover {{
    background-color: {C_DANGER}44;
}}

/* ── Labels ── */
QLabel {{
    background: transparent;
    color: {C_TEXT_MAIN};
}}
QLabel#sectionHeader {{
    color: {C_TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}
QLabel#monoLabel {{
    font-family: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
    font-size: 11px;
    color: {C_TEXT_SECONDARY};
}}

/* ── Separator ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {C_BORDER_SOFT};
    background: {C_BORDER_SOFT};
    max-height: 1px;
    border: none;
}}

/* ── Status bar ── */
QStatusBar {{
    background: {C_PANEL_BG};
    color: {C_TEXT_MUTED};
    font-family: "JetBrains Mono", "SF Mono", Menlo, monospace;
    font-size: 11px;
    border-top: 1px solid {C_BORDER_SOFT};
}}
"""
