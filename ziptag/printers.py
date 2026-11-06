"""Printer, material and nozzle definitions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ziptag.layout import Rect

PLATE_MARGIN = 5.0   # tags stay this far from the plate edge


class Material(StrEnum):
    PLA = "PLA"
    PETG = "PETG"
    ABS = "ABS"


class Nozzle(StrEnum):
    NORMAL = "Normal"
    HIGH_FLOW = "High Flow"


@dataclass(frozen=True)
class Printer:
    """A target printer. ``bambu`` printers get a Bambu Studio project; others a plain 3MF."""

    key: str
    label: str
    bed_x: float
    bed_y: float
    bambu: bool = True
    dual_nozzle: bool = False       # H2D / H2C style (two extruders)
    # (x0, y0, x1, y1) of the area every nozzle can reach; None = whole bed minus the plate margin
    usable: tuple[float, float, float, float] | None = None
    # rectangles (x0, y0, x1, y1) the printer cannot use, e.g. the X1/P1 front-left corner
    exclusions: tuple[tuple[float, float, float, float], ...] = ()

    def usable_rect(self) -> Rect:
        """The area tags may occupy."""
        if self.usable:
            return Rect(*self.usable)
        return Rect(PLATE_MARGIN, PLATE_MARGIN, self.bed_x - PLATE_MARGIN, self.bed_y - PLATE_MARGIN)

    def dead_zones(self) -> tuple[Rect, ...]:
        """Areas of the bed the printer cannot use."""
        return tuple(Rect(*r) for r in self.exclusions)


_X1_CORNER = ((0, 0, 18, 28),)   # front-left corner of the X1/P1 bed is unusable

BAMBU_PRINTERS: tuple[Printer, ...] = (
    Printer("A1", "Bambu Lab A1", 256, 256),
    Printer("X1", "Bambu Lab X1 / X1 Carbon", 256, 256, exclusions=_X1_CORNER),
    Printer("P1S", "Bambu Lab P1S", 256, 256, exclusions=_X1_CORNER),
    Printer("P1P", "Bambu Lab P1P", 256, 256, exclusions=_X1_CORNER),
    # H2 series: the left nozzle reaches x 0-325 and the right nozzle x 25-(bed-0); the top strip
    # y > 310 is the nozzle-wipe area.  Tags use both nozzles, so stay inside the overlap.
    Printer("H2C", "Bambu Lab H2C", 330, 320, dual_nozzle=True, usable=(30, 5, 320, 305)),
    Printer("H2D", "Bambu Lab H2D", 350, 320, dual_nozzle=True, usable=(30, 5, 320, 305)),
)

CUSTOM_KEY = "CUSTOM"


def custom_printer(bed_x: float, bed_y: float) -> Printer:
    """A non-Bambu printer with a user-supplied bed size (plain 3MF output)."""
    return Printer(CUSTOM_KEY, "Other printer (plain 3MF)", bed_x, bed_y, bambu=False)


def printer_by_label(label: str) -> Printer | None:
    for printer in BAMBU_PRINTERS:
        if printer.label == label:
            return printer
    return None
