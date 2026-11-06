"""Tag geometry: dimensions, text fitting and mesh construction."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
from manifold3d import CrossSection, FillRule, JoinType, Manifold, OpType

from ziptag import constants as c
from ziptag.fonts import FontFace


class Align(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


@dataclass(frozen=True)
class TagSpec:
    """Everything that defines one tag."""

    text: str
    size_pct: float = c.SIZE_DEFAULT_PCT        # tag footprint scale (50-150)
    text_pct: float | None = None               # None = auto-fit; else % of default text size
    align: Align = Align.CENTER


@dataclass(frozen=True)
class Dimensions:
    """Tag footprint in mm."""

    length: float
    width: float
    thickness: float = c.THICKNESS

    @property
    def label_length(self) -> float:
        return self.length - c.ZIP_SECTION


def dimensions(size_pct: float) -> Dimensions:
    """Footprint for a size percentage; thickness and the zip-tie slot never change."""
    scale = size_pct / 100.0
    return Dimensions(length=c.ZIP_SECTION + c.BASE_LABEL_LENGTH * scale,
                      width=c.BASE_WIDTH * scale)


class FitStatus(StrEnum):
    OK = "ok"
    SHRUNK = "shrunk"          # auto-fit reduced the text size to make it fit
    TOO_SMALL = "small"        # fits, but cap height is below the legible limit
    OVERFLOW = "overflow"      # will be clipped at the tag edge


@dataclass(frozen=True)
class TextFit:
    """Result of fitting a tag's text into its label area."""

    pct: float                 # text size actually used (% of default)
    cap_mm: float              # resulting cap height
    status: FitStatus
    message: str
    overflow_mm: float = 0.0

    @property
    def warning(self) -> bool:
        return self.status in (FitStatus.OVERFLOW, FitStatus.TOO_SMALL)


@dataclass
class TagMesh:
    """A built tag: body and text inlay solids in tag-local coordinates (origin at a corner)."""

    spec: TagSpec
    dims: Dimensions
    fit: TextFit
    body: Manifold
    inlay: Manifold | None
    stats: dict = field(default_factory=dict)


def _text_outline(face: FontFace, text: str) -> tuple[list[np.ndarray], float]:
    """Glyph contours laid out on one line, in font units, plus the line's ink bbox width."""
    tracking = c.TRACKING_EM * face.cap_height
    polys: list[np.ndarray] = []
    x = 0.0
    for char in text:
        glyph = face.glyph(char)
        for contour in glyph.contours:
            polys.append(contour + np.array([x, 0.0]))
        x += glyph.advance + tracking
    return polys, x


def _ink_bounds(polys: list[np.ndarray]) -> tuple[float, float, float, float]:
    pts = np.vstack(polys)
    return pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()


def fit_text(face: FontFace, spec: TagSpec) -> TextFit:
    """Decide the text size for a tag and report whether it fits.

    Cheap (no mesh work), so the UI can call it on every edit.
    """
    text = spec.text.strip()
    dims = dimensions(spec.size_pct)
    scale = spec.size_pct / 100.0
    default_cap = c.BASE_CAP_HEIGHT * scale
    if not text:
        return TextFit(100.0, default_cap, FitStatus.OK, "Empty (no text)")

    polys, _ = _text_outline(face, text)
    x0, x1, y0, y1 = _ink_bounds(polys)
    ink_w, ink_h = x1 - x0, y1 - y0
    avail_w = dims.label_length - 2 * c.MARGIN_X
    avail_h = dims.width - 2 * c.MARGIN_Y

    def cap_for(pct: float) -> float:
        return default_cap * pct / 100.0

    def ink_mm(pct: float) -> tuple[float, float]:
        k = cap_for(pct) / face.cap_height
        return ink_w * k, ink_h * k

    if spec.text_pct is None:
        # largest size (<= 100 %) at which the ink fits both ways
        by_w = avail_w / ink_w * face.cap_height / default_cap * 100.0
        by_h = avail_h / ink_h * face.cap_height / default_cap * 100.0
        fit_pct = min(100.0, by_w, by_h)
        pct = float(max(c.AUTO_MIN_PCT, fit_pct))
    else:
        pct = float(np.clip(spec.text_pct, c.MANUAL_MIN_PCT, c.MANUAL_MAX_PCT))

    w_mm, h_mm = ink_mm(pct)
    over = max(w_mm - avail_w, 0.0)
    over_h = max(h_mm - avail_h, 0.0)
    cap = cap_for(pct)
    if over > 0.05 or over_h > 0.05:
        what = f"{over:.1f} mm too wide" if over >= over_h else f"{over_h:.1f} mm too tall"
        return TextFit(pct, cap, FitStatus.OVERFLOW,
                       f"Spills over ({what}) - will be clipped. Shorten, lower size or enlarge tag.",
                       float(max(over, over_h)))
    if cap < c.LEGIBLE_CAP_MM:
        return TextFit(pct, cap, FitStatus.TOO_SMALL,
                       f"Text is very small (cap height {cap:.1f} mm) - may not print cleanly.")
    if spec.text_pct is None and pct < 99.5:
        return TextFit(pct, cap, FitStatus.SHRUNK, f"Auto-shrunk to {pct:.0f}% to fit")
    return TextFit(pct, cap, FitStatus.OK, "OK")


def place_text(face: FontFace, spec: TagSpec, fit: TextFit, dims: Dimensions) -> list[np.ndarray]:
    """Text contours positioned on the tag in millimetres (before cleanup and clipping)."""
    polys, _ = _text_outline(face, spec.text.strip())
    x0, x1, y0, y1 = _ink_bounds(polys)
    k = fit.cap_mm / face.cap_height
    area_x0 = c.ZIP_SECTION + c.MARGIN_X
    area_x1 = dims.length - c.MARGIN_X
    ink_w = (x1 - x0) * k
    if spec.align is Align.LEFT:
        left = area_x0
    elif spec.align is Align.RIGHT:
        left = area_x1 - ink_w
    else:
        left = (area_x0 + area_x1 - ink_w) / 2.0
    bottom = (dims.width - (y1 - y0) * k) / 2.0
    shift = np.array([left - x0 * k, bottom - y0 * k])
    return [p * k + shift for p in polys]


def _text_cross_section(face: FontFace, spec: TagSpec, fit: TextFit, dims: Dimensions) -> CrossSection:
    """Cleaned-up, clipped text outline ready to extrude."""
    section = CrossSection(place_text(face, spec, fit, dims), FillRule.NonZero)
    r = c.CLEAN_RADIUS
    # close (fill sub-nozzle slivers) then open (round sub-nozzle spikes)
    section = section.offset(r, JoinType.Round, 2.0, 32).offset(-r, JoinType.Round, 2.0, 32)
    section = section.offset(-r, JoinType.Round, 2.0, 32).offset(r, JoinType.Round, 2.0, 32)
    clip = CrossSection.square((dims.length - c.ZIP_SECTION - 2 * c.WALL,
                                dims.width - 2 * c.WALL)).translate((c.ZIP_SECTION + c.WALL, c.WALL))
    return CrossSection.batch_boolean([section, clip], OpType.Intersect)


def build_tag(face: FontFace, spec: TagSpec) -> TagMesh:
    """Build the body (with text recess and zip-tie slot) and the matching text inlay."""
    dims = dimensions(spec.size_pct)
    fit = fit_text(face, spec)
    body = Manifold.cube((dims.length, dims.width, dims.thickness))
    slot = Manifold.cube((c.SLOT_X1 - c.SLOT_X0, dims.width + 2, c.SLOT_Z1 - c.SLOT_Z0))
    body = body - slot.translate((c.SLOT_X0, -1, c.SLOT_Z0))

    inlay = None
    if spec.text.strip():
        section = _text_cross_section(face, spec, fit, dims)
        if not section.is_empty():
            z0 = dims.thickness - c.TEXT_DEPTH
            inlay = Manifold.extrude(section, c.TEXT_DEPTH).translate((0, 0, z0))
            cutter = Manifold.extrude(section, c.TEXT_DEPTH + 0.2).translate((0, 0, z0))
            body = body - cutter
    return TagMesh(spec, dims, fit, body, inlay)
