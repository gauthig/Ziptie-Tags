"""Developer tool: build the Bambu Studio project-settings templates shipped in ``templates/``.

Needs Bambu Studio installed (its system profiles) and two Studio-saved projects as shape
references (a dual-nozzle H2D project and a single-nozzle P1S project).  The result is one
gzip-compressed JSON per printer/material/nozzle, so the finished app needs neither Studio nor
the reference projects.

Usage: python tools/make_templates.py --h2d-ref <h2d.3mf> --p1s-ref <p1s.3mf>
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import zipfile
from functools import cache
from pathlib import Path

PROFILE_ROOT = Path(os.path.expandvars(r"%APPDATA%\BambuStudio\system\BBL"))
OUT_DIR = Path(__file__).resolve().parents[1] / "templates"
NFIL = 2
PROJECT_FILE = "Metadata/project_settings.config"
META_KEYS = {"type", "name", "inherits", "from", "setting_id", "instantiation", "description", "version",
             "compatible_printers", "compatible_printers_condition", "compatible_prints",
             "compatible_prints_condition", "filament_id", "base_id"}
# keys that exist in both machine and filament presets: the machine meaning wins
SHARED_MACHINE_KEYS = {"long_retractions_when_ec", "retraction_distances_when_ec"}

# printer key -> (machine profile, process profile, reference family, filament family search order)
PRINTERS = {
    "A1": ("Bambu Lab A1 0.4 nozzle", "0.20mm Standard @BBL A1", "single", ["A1"]),
    "X1": ("Bambu Lab X1 Carbon 0.4 nozzle", "0.20mm Standard @BBL X1C", "single", ["X1C"]),
    "P1S": ("Bambu Lab P1S 0.4 nozzle", "0.20mm Standard @BBL X1C", "single", ["P1S", "X1C"]),
    "P1P": ("Bambu Lab P1P 0.4 nozzle", "0.20mm Standard @BBL P1P", "single", ["P1P", "P1S", "X1C"]),
    "H2C": ("Bambu Lab H2C 0.4 nozzle", "0.20mm Standard @BBL H2C", "dual", ["H2C"]),
    "H2D": ("Bambu Lab H2D 0.4 nozzle", "0.20mm Standard @BBL H2D", "dual", ["H2D"]),
}
MATERIALS = {"PLA": "PLA Basic", "PETG": "PETG Basic", "ABS": "ABS"}


@cache
def _index(kind: str) -> dict[str, dict]:
    index = {}
    for path in glob.glob(str(PROFILE_ROOT / kind / "*.json")):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if "name" in data:
            index[data["name"]] = data
    return index


def flatten(kind: str, name: str) -> dict:
    """Resolve a system preset with all its inherited values."""
    data = _index(kind)[name]
    out = flatten(kind, data["inherits"]) if data.get("inherits") else {}
    out.update(data)
    return out


def filament_profile_name(material: str, families: list[str]) -> str:
    base = MATERIALS[material]
    for family in families:
        for suffix in (" 0.4 nozzle", ""):
            name = f"Bambu {base} @BBL {family}{suffix}"
            if name in _index("filament"):
                return name
    raise KeyError(f"no filament profile for {material} / {families}")


def load_reference(path: str) -> dict:
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read(PROJECT_FILE))


def trim_filaments(base: dict, machine_keys: set[str], keep: int) -> dict:
    """Cut a many-filament project down to its first ``keep`` filaments (shape-preserving)."""
    n0 = len(base["filament_colour"])
    out = dict(base)
    for key, value in base.items():
        if not isinstance(value, list) or key in machine_keys or key in SHARED_MACHINE_KEYS:
            continue
        if key in ("flush_volumes_matrix", "flush_volumes_vector"):
            continue
        if len(value) >= n0 and len(value) % n0 == 0:
            per = len(value) // n0
            out[key] = value[:keep * per]
    # flush volumes: one n0 x n0 matrix (and n0 vector) per extruder
    matrix, vector = base["flush_volumes_matrix"], base["flush_volumes_vector"]
    extruders = len(matrix) // (n0 * n0)
    out["flush_volumes_matrix"] = [matrix[e * n0 * n0 + i * n0 + j]
                                   for e in range(extruders) for i in range(keep) for j in range(keep)]
    out["flush_volumes_vector"] = [vector[e * n0 + i] for e in range(len(vector) // n0) for i in range(keep)]
    for e in range(extruders):                      # the reference holds a stray value on a diagonal
        for i in range(keep):
            out["flush_volumes_matrix"][e * keep * keep + i * keep + i] = "0"
    return out


def fit_len(values: list, size: int) -> list:
    """Repeat/truncate ``values`` to exactly ``size`` entries."""
    if len(values) >= size:
        return values[:size]
    return values + [values[-1]] * (size - len(values))


def build_template(printer: str, material: str, h2d_ref: dict, p1s_ref: dict) -> dict:
    machine_name, process_name, shape, families = PRINTERS[printer]
    machine = flatten("machine", machine_name)
    process = flatten("process", process_name)
    fil_name = filament_profile_name(material, families)
    filament = flatten("filament", fil_name)
    base = h2d_ref if shape == "dual" else p1s_ref

    machine_keys = {k for k in machine if k not in META_KEYS}
    settings = trim_filaments(base, machine_keys, NFIL)

    # printer + process presets: natural shapes from the system profiles
    for key, value in list(machine.items()) + list(process.items()):
        if key in META_KEYS:
            continue
        settings[key] = value

    # filament preset: per-filament entries use the preset's own variant list
    variants = len(settings["filament_extruder_variant"]) // NFIL if "filament_extruder_variant" in settings else 1
    for key, value in filament.items():
        if key in META_KEYS or key in SHARED_MACHINE_KEYS or key not in settings:
            continue
        if isinstance(value, list):
            settings[key] = fit_len(value, variants) * NFIL if isinstance(settings[key], list) else value
        else:
            settings[key] = value
    settings["filament_settings_id"] = [fil_name] * NFIL
    settings["filament_ids"] = [filament.get("filament_id", "GFL99")] * NFIL
    settings["filament_type"] = [filament["filament_type"][0]] * NFIL
    settings["filament_colour"] = ["#1A1A1A", "#FF6600"]
    settings["default_filament_colour"] = [""] * NFIL
    settings["print_compatible_printers"] = process["compatible_printers"]
    settings["printer_settings_id"] = machine_name
    settings["print_settings_id"] = process_name
    settings["curr_bed_type"] = "Textured PEI Plate"
    settings["different_settings_to_system"] = [""] * (NFIL + 2)
    settings["inherits_group"] = [""] * (NFIL + 2)
    return settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h2d-ref", required=True)
    parser.add_argument("--p1s-ref", required=True)
    parser.add_argument("--only", help="printer key to build (default: all)")
    args = parser.parse_args()
    h2d_ref, p1s_ref = load_reference(args.h2d_ref), load_reference(args.p1s_ref)
    OUT_DIR.mkdir(exist_ok=True)
    for printer in PRINTERS:
        if args.only and printer != args.only:
            continue
        for material in MATERIALS:
            settings = build_template(printer, material, h2d_ref, p1s_ref)
            path = OUT_DIR / f"{printer}_{material}.json.gz"
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                json.dump(settings, fh, separators=(",", ":"))
            print("wrote", path.name, len(settings), "keys")


if __name__ == "__main__":
    main()
