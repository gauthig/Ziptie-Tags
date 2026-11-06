"""Arrange tags onto one or more build plates (simple shelf packing)."""
from __future__ import annotations

from dataclasses import dataclass

TAG_GAP = 4.0


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    def overlaps(self, other: Rect) -> bool:
        return self.x0 < other.x1 and other.x0 < self.x1 and self.y0 < other.y1 and other.y0 < self.y1


@dataclass(frozen=True)
class Placement:
    """Where tag number ``index`` goes on a plate (lower-left corner, plate coordinates)."""

    index: int
    x: float
    y: float


class LayoutError(ValueError):
    """A tag cannot fit on an empty plate."""


def pack(sizes: list[tuple[float, float]], usable: Rect,
         keepouts: tuple[Rect, ...] = ()) -> list[list[Placement]]:
    """Place (length, width) tags row by row; start a new plate when a plate is full.

    ``usable`` is the area tags may occupy; ``keepouts`` (prime tower, printer dead zones)
    must stay empty on every plate.  Tag order is preserved: plate 1 holds the first tags.
    """
    plates: list[list[Placement]] = []
    for index, (length, width) in enumerate(sizes):
        if length > usable.x1 - usable.x0 or width > usable.y1 - usable.y0:
            raise LayoutError(f"Tag {index + 1} ({length:.0f} x {width:.0f} mm) does not fit on the "
                              f"{usable.x1 - usable.x0:.0f} x {usable.y1 - usable.y0:.0f} mm usable plate area.")
    cursor = _Cursor(usable, keepouts)
    plate: list[Placement] = []
    for index, (length, width) in enumerate(sizes):
        pos = cursor.place(length, width)
        if pos is None:
            plates.append(plate)
            plate = []
            cursor = _Cursor(usable, keepouts)
            pos = cursor.place(length, width)
            if pos is None:  # pragma: no cover - guarded by the size check above plus keepout
                raise LayoutError(f"Tag {index + 1} cannot be placed around the reserved area.")
        plate.append(Placement(index, *pos))
    if plate:
        plates.append(plate)
    return plates


class _Cursor:
    """Row-by-row placement state for one plate."""

    def __init__(self, usable: Rect, keepouts: tuple[Rect, ...]):
        self.usable = usable
        self.keepouts = tuple(_grow(k) for k in keepouts)
        self.x = usable.x0
        self.y = usable.y0
        self.row_height = 0.0

    def place(self, length: float, width: float) -> tuple[float, float] | None:
        while True:
            if self.x + length > self.usable.x1:          # row is full -> next row
                self.y += self.row_height + TAG_GAP
                self.x = self.usable.x0
                self.row_height = 0.0
                continue
            if self.y + width > self.usable.y1:
                return None
            box = Rect(self.x, self.y, self.x + length, self.y + width)
            blockers = [k for k in self.keepouts if box.overlaps(k)]
            if blockers:
                self.x = max(k.x1 for k in blockers)        # hop over the reserved area
                continue
            self.row_height = max(self.row_height, width)
            pos = (self.x, self.y)
            self.x += length + TAG_GAP
            return pos


def _grow(rect: Rect) -> Rect:
    """Keep tags one gap away from a reserved area."""
    return Rect(rect.x0 - TAG_GAP, rect.y0 - TAG_GAP, rect.x1 + TAG_GAP, rect.y1 + TAG_GAP)
