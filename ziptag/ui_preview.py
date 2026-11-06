"""Top-down preview of one tag (to scale)."""
from __future__ import annotations

import tkinter as tk

from ziptag import constants as c
from ziptag.fonts import FontFace
from ziptag.geometry import FitStatus, TagSpec, dimensions, fit_text, place_text

BODY = "#2b2b2b"
TEXT = "#ff6600"
TEXT_BAD = "#e02020"
SLOT = "#9a9a9a"
PAD = 14


class TagPreview(tk.Canvas):
    """Draws the tag outline, zip-tie slot and text exactly as they will be printed."""

    def __init__(self, master, height: int = 150):
        super().__init__(master, height=height, background="#f4f4f4", highlightthickness=1,
                         highlightbackground="#c8c8c8")
        self._last: tuple[FontFace, TagSpec] | None = None
        self.bind("<Configure>", lambda _e: self._redraw())

    def show(self, face: FontFace, spec: TagSpec) -> None:
        self._last = (face, spec)
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        if self._last is None:
            return
        face, spec = self._last
        dims = dimensions(spec.size_pct)
        avail_w = max(self.winfo_width() - 2 * PAD, 50)
        avail_h = max(self.winfo_height() - 2 * PAD, 30)
        scale = min(avail_w / dims.length, avail_h / dims.width)
        ox = (self.winfo_width() - dims.length * scale) / 2.0
        oy = (self.winfo_height() + dims.width * scale) / 2.0

        def px(x: float, y: float) -> tuple[float, float]:
            return ox + x * scale, oy - y * scale        # flip Y: tag origin is bottom-left

        x0, y0 = px(0, dims.width)
        x1, y1 = px(dims.length, 0)
        self.create_rectangle(x0, y0, x1, y1, fill=BODY, outline="")
        sx0, sy0 = px(c.SLOT_X0, dims.width)
        sx1, sy1 = px(c.SLOT_X1, 0)
        self.create_rectangle(sx0, sy0, sx1, sy1, outline=SLOT, dash=(3, 3))
        self.create_text((sx0 + sx1) / 2, (sy0 + sy1) / 2, text="zip tie", fill=SLOT, font=("Segoe UI", 8))

        if not spec.text.strip():
            return
        fit = fit_text(face, spec)
        colour = TEXT_BAD if fit.status is FitStatus.OVERFLOW else TEXT
        for poly in place_text(face, spec, fit, dims):
            coords = [v for point in poly for v in px(point[0], point[1])]
            self.create_polygon(coords, fill=colour, outline=colour)
        # the printed text is clipped this far from the edge: show that limit while overflowing
        if fit.status is FitStatus.OVERFLOW:
            cx0, cy0 = px(c.ZIP_SECTION + c.WALL, dims.width - c.WALL)
            cx1, cy1 = px(dims.length - c.WALL, c.WALL)
            self.create_rectangle(cx0, cy0, cx1, cy1, outline=TEXT_BAD, dash=(4, 3))
