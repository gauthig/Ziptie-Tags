"""Turn a list of tag specs into a finished 3MF file."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ziptag.bambu_3mf import load_settings, prime_tower_width, write_bambu_3mf
from ziptag.fonts import load_font
from ziptag.geometry import TagMesh, TagSpec, build_tag, dimensions
from ziptag.layout import Placement, Rect, pack
from ziptag.plain_3mf import write_plain_3mf
from ziptag.printers import Material, Nozzle, Printer
from ziptag.stl import write_stl

TOWER_DEPTH = 45.0   # footprint reserved for the prime tower, away from the tags


@dataclass(frozen=True)
class JobOptions:
    """Everything the user chose except the per-tag rows."""

    font_path: Path
    printer: Printer
    material: Material = Material.PETG
    nozzle: Nozzle = Nozzle.NORMAL


def tower_area(printer: Printer, material: Material) -> Rect:
    """Prime-tower area (back-right corner of the usable plate) for a Bambu printer."""
    area = printer.usable_rect()
    width = prime_tower_width(load_settings(printer, material))
    return Rect(area.x1 - width, area.y1 - TOWER_DEPTH, area.x1, area.y1)


def plan_plates(specs: list[TagSpec], opts: JobOptions, tower: bool = True) -> list[list[Placement]]:
    """Decide which tag goes where (no geometry needed, so this is fast).

    ``tower`` reserves the prime-tower area; Bambu projects need it, STL export does not.
    """
    sizes = [(d.length, d.width) for d in (dimensions(s.size_pct) for s in specs)]
    printer = opts.printer
    keepouts = list(printer.dead_zones())
    if printer.bambu and tower:
        keepouts.append(tower_area(printer, opts.material))
    return pack(sizes, printer.usable_rect(), tuple(keepouts))


def _build_plates(specs: list[TagSpec], opts: JobOptions, tower: bool) -> list[list[tuple[TagMesh, Placement]]]:
    """Lay out the tags and build their geometry, plate by plate."""
    plates = plan_plates(specs, opts, tower)
    face = load_font(opts.font_path)
    meshes: dict[int, TagMesh] = {}
    built: list[list[tuple[TagMesh, Placement]]] = []
    for plate in plates:
        items = []
        for place in plate:
            if place.index not in meshes:
                meshes[place.index] = build_tag(face, specs[place.index])
            items.append((meshes[place.index], place))
        built.append(items)
    return built


def build_stl(specs: list[TagSpec], opts: JobOptions, path: Path) -> int:
    """Write all tags into one STL (plates side by side). Returns the number of plates."""
    built = _build_plates(specs, opts, tower=False)
    write_stl(path, built, opts.printer.bed_x)
    return len(built)


def build_job(specs: list[TagSpec], opts: JobOptions, path: Path) -> int:
    """Build every tag and write the 3MF. Returns the number of plates."""
    built = _build_plates(specs, opts, tower=True)
    if opts.printer.bambu:
        write_bambu_3mf(path, built, opts.printer, opts.material, opts.nozzle,
                        tower_area(opts.printer, opts.material))
    else:
        write_plain_3mf(path, built, opts.printer.bed_x)
    return len(built)
