"""Embedded fonts: discovery and glyph-outline extraction."""
# ruff: noqa: N802, N815  (the pen hook names below are fontTools' own API)
from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

from ziptag.constants import CURVE_STEPS

FALLBACK_CHAR = "?"


def resource_dir(name: str) -> Path:
    """Return a bundled resource folder (works from source and from a PyInstaller exe)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / name


def available_fonts() -> dict[str, Path]:
    """Map display name -> TTF path for every bundled font, sorted by name."""
    found = {}
    for path in sorted(resource_dir("fonts").glob("*-Bold.ttf")):
        found[_display_name(path)] = path
    return found


def _display_name(path: Path) -> str:
    """'SourceSans3-Bold.ttf' -> 'Source Sans 3' (read from the font's own name table)."""
    font = TTFont(path, lazy=True)
    family = font["name"].getBestFamilyName()
    font.close()
    return family


class _FlattenPen(BasePen):
    """Collect glyph contours as polylines, flattening quadratic curves."""

    def __init__(self, glyph_set):
        super().__init__(glyph_set)
        self.contours: list[list[tuple[float, float]]] = []
        self._current: list[tuple[float, float]] = []

    def _moveTo(self, pt):
        self._current = [pt]

    def _lineTo(self, pt):
        self._current.append(pt)

    def _qCurveToOne(self, pt1, pt2):
        p0 = self._current[-1]
        for i in range(1, CURVE_STEPS + 1):
            t = i / CURVE_STEPS
            u = 1.0 - t
            self._current.append((u * u * p0[0] + 2 * u * t * pt1[0] + t * t * pt2[0],
                                  u * u * p0[1] + 2 * u * t * pt1[1] + t * t * pt2[1]))

    def _closePath(self):
        if len(self._current) > 2:
            self.contours.append(self._current)
        self._current = []

    _endPath = _closePath


@dataclass(frozen=True)
class Glyph:
    """One glyph: contours in font units plus its horizontal advance."""

    contours: tuple[np.ndarray, ...]
    advance: float


class FontFace:
    """A loaded TrueType font that yields glyph outlines in font units."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._font = TTFont(self.path)
        self._cmap = self._font.getBestCmap()
        self._glyph_set = self._font.getGlyphSet()
        self._hmtx = self._font["hmtx"]
        self.units_per_em: int = self._font["head"].unitsPerEm
        self._cache: dict[str, Glyph] = {}
        self.cap_height: float = self._measure_cap_height()

    def has_char(self, char: str) -> bool:
        return ord(char) in self._cmap

    def glyph(self, char: str) -> Glyph:
        """Return the glyph for ``char`` (the fallback glyph if the font lacks it)."""
        if not self.has_char(char):
            char = FALLBACK_CHAR
        if char not in self._cache:
            name = self._cmap[ord(char)]
            pen = _FlattenPen(self._glyph_set)
            self._glyph_set[name].draw(pen)
            contours = tuple(np.asarray(c, dtype=float) for c in pen.contours)
            self._cache[char] = Glyph(contours, float(self._hmtx[name][0]))
        return self._cache[char]

    def _measure_cap_height(self) -> float:
        pts = np.vstack(self.glyph("H").contours)
        return float(pts[:, 1].max())


@lru_cache(maxsize=16)
def load_font(path: Path) -> FontFace:
    """Load (and memoise) a font file."""
    return FontFace(path)
