"""Generate assets/icons/parallax-studio.png from the in-app LogoWidget mark.

The app icon and the mark in the top bar are the same drawing, so they cannot
drift apart. Run from the project root:

    python tools/make_app_icon.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication

from app.ui.theme import C_ACCENT

SIZE = 1024
OUT = Path(__file__).resolve().parent.parent / "assets" / "icons" / "parallax-studio.png"

# LogoWidget draws on a 42x42 widget; its mark occupies roughly x/y 4..39.
MARK_BOX = 42.0
MARK_FRACTION = 0.62  # how much of the icon the mark fills


def draw_mark(p: QPainter, scale: float, dx: float, dy: float) -> None:
    """The same geometry as app.ui.main_window.LogoWidget.paintEvent."""
    p.save()
    p.translate(dx, dy)
    p.scale(scale, scale)

    grad = QLinearGradient(QPointF(4, 4), QPointF(38, 38))
    grad.setColorAt(0, QColor(C_ACCENT))
    grad.setColorAt(1, QColor("#167F77"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(4, 4, 30, 34), 4, 4)

    p.setBrush(QColor("#091013"))
    p.drawRect(QRectF(15, 12, 6, 22))

    p.setBrush(QColor(C_ACCENT))
    p.drawPie(QRectF(15, 5, 24, 24), -90 * 16, 180 * 16)

    p.setBrush(QColor("#0B1014"))
    p.drawPie(QRectF(21, 11, 12, 12), -90 * 16, 180 * 16)
    p.restore()


def main() -> None:
    app = QApplication.instance() or QApplication([])

    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))

    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Dark rounded plate so the cyan mark reads on any desktop wallpaper.
    plate = QLinearGradient(QPointF(0, 0), QPointF(SIZE, SIZE))
    plate.setColorAt(0.0, QColor("#16222B"))
    plate.setColorAt(1.0, QColor("#0A0F13"))
    p.setBrush(QBrush(plate))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0, 0, SIZE, SIZE), SIZE * 0.18, SIZE * 0.18)

    # Hairline edge, same border tone the UI uses.
    p.setBrush(Qt.BrushStyle.NoBrush)
    pen_w = SIZE * 0.006
    p.setPen(QColor("#24313C"))
    p.drawRoundedRect(
        QRectF(pen_w / 2, pen_w / 2, SIZE - pen_w, SIZE - pen_w),
        SIZE * 0.18,
        SIZE * 0.18,
    )

    scale = (SIZE * MARK_FRACTION) / MARK_BOX
    offset = (SIZE - MARK_BOX * scale) / 2.0
    # LogoWidget's mark sits slightly left/low inside its 42x42 box; nudge it
    # back to the optical centre.
    draw_mark(p, scale, offset - SIZE * 0.012, offset + SIZE * 0.006)
    p.end()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(OUT))
    print(f"wrote {OUT} ({SIZE}x{SIZE})")


if __name__ == "__main__":
    main()
