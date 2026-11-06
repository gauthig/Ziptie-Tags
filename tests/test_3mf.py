"""3MF output: structure, Bambu-native markers, plain 3MF cleanliness, multi-plate."""
from __future__ import annotations

import json
import zipfile

import pytest

from ziptag import constants as c
from ziptag.geometry import TagSpec
from ziptag.printers import BAMBU_PRINTERS, Material, Nozzle, custom_printer
from ziptag.project import JobOptions, build_job

SPECS = [TagSpec("HEX BEAM"), TagSpec("VERTICAL")]


def _printer(key):
    return next(p for p in BAMBU_PRINTERS if p.key == key)


def _settings(path):
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read("Metadata/project_settings.config"))


@pytest.mark.parametrize("printer", BAMBU_PRINTERS, ids=lambda p: p.key)
@pytest.mark.parametrize("material", list(Material))
def test_bambu_project_is_consistent(tmp_path, fonts, printer, material):
    out = tmp_path / "t.3mf"
    build_job(SPECS, JobOptions(fonts["Roboto"], printer, material), out)
    with zipfile.ZipFile(out) as z:
        assert "BambuStudio-" in z.read("3D/3dmodel.model").decode()
        ranges = z.read("Metadata/layer_config_ranges.xml").decode()
        assert f'min_z="{c.Z_SWITCH}"' in ranges and f'max_z="{c.THICKNESS}"' in ranges
    s = _settings(out)
    assert s["filament_type"] == [material.value] * 2
    assert s["filament_colour"] == ["#1A1A1A", "#FF6600"]
    assert s["layer_height"] == "0.2"
    assert s["printable_area"][2] == f"{printer.bed_x:g}x{printer.bed_y:g}"
    assert s["printer_settings_id"].startswith("Bambu Lab")
    sizes = {len(s[k]) for k in ("nozzle_temperature", "filament_flow_ratio", "filament_max_volumetric_speed")}
    assert len(sizes) == 1 and sizes.pop() % 2 == 0     # same, whole number of entries per filament
    if "filament_extruder_variant" in s:
        assert len(s["filament_extruder_variant"]) == len(s["nozzle_temperature"])


@pytest.mark.parametrize("nozzle,expect", [(Nozzle.NORMAL, "Standard"), (Nozzle.HIGH_FLOW, "High Flow")])
def test_dual_nozzle_type(tmp_path, fonts, nozzle, expect):
    out = tmp_path / "t.3mf"
    build_job(SPECS, JobOptions(fonts["Roboto"], _printer("H2D"), Material.PETG, nozzle), out)
    s = _settings(out)
    assert s["nozzle_volume_type"] == [expect, expect]
    assert s["extruder_nozzle_stats"] == [f"{expect}#1"] * 2


def test_plain_3mf_has_no_bambu_content(tmp_path, fonts):
    out = tmp_path / "plain.3mf"
    build_job(SPECS, JobOptions(fonts["Roboto"], custom_printer(220, 220)), out)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert names == ["[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"]
        blob = b"".join(z.read(n) for n in names).lower()
    assert b"bambu" not in blob and b"project_settings" not in blob


def test_multi_plate_bambu_assigns_every_tag(tmp_path, fonts):
    specs = [TagSpec(f"TAG {i}", size_pct=150) for i in range(40)]
    out = tmp_path / "multi.3mf"
    plates = build_job(specs, JobOptions(fonts["Roboto"], _printer("P1S")), out)
    assert plates >= 2
    with zipfile.ZipFile(out) as z:
        cfg = z.read("Metadata/model_settings.config").decode()
    assert cfg.count("<plate>") == plates and cfg.count("<model_instance>") == 40
    assert len(_settings(out)["wipe_tower_x"]) == plates


def test_text_part_uses_second_filament(tmp_path, fonts):
    out = tmp_path / "t.3mf"
    build_job(SPECS, JobOptions(fonts["Roboto"], _printer("A1")), out)
    with zipfile.ZipFile(out) as z:
        cfg = z.read("Metadata/model_settings.config").decode()
    assert cfg.count('<metadata key="extruder" value="2"/>') == 2


@pytest.mark.parametrize("printer", [_printer("H2D"), custom_printer(220, 220)], ids=["bambu", "plain"])
def test_special_characters_produce_well_formed_xml(tmp_path, fonts, printer):
    from xml.etree import ElementTree

    out = tmp_path / "t.3mf"
    build_job([TagSpec('A&B <1> "x"')], JobOptions(fonts["Roboto"], printer), out)
    with zipfile.ZipFile(out) as z:
        for name in z.namelist():
            if name.endswith((".model", ".config", ".xml", ".rels")) and name != "Metadata/project_settings.config":
                ElementTree.fromstring(z.read(name))


def test_stl_has_all_tags_and_is_valid(tmp_path, fonts):
    import struct

    import numpy as np

    from ziptag.project import build_stl

    out = tmp_path / "t.stl"
    specs = [TagSpec(f"TAG {i}") for i in range(5)]
    plates = build_stl(specs, JobOptions(fonts["Roboto"], _printer("H2D")), out)
    data = out.read_bytes()
    count = struct.unpack("<I", data[80:84])[0]
    assert plates == 1 and len(data) == 84 + 50 * count and count > 1000
    tris = np.frombuffer(data[84:], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))["v"]
    assert tris[:, :, 2].min() >= -1e-4 and tris[:, :, 2].max() == pytest.approx(c.THICKNESS, abs=1e-3)
