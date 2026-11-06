"""Bambu Studio-native 3MF writer (project settings, plates, per-object layer ranges)."""
from __future__ import annotations

import gzip
import json
import math
import zipfile
from pathlib import Path

import numpy as np

from ziptag import __version__
from ziptag import constants as c
from ziptag.fonts import resource_dir
from ziptag.geometry import TagMesh
from ziptag.layout import Placement, Rect
from ziptag.mesh import MeshData, new_uuid, to_mesh, triangles_xml, vertices_xml, xml_attr
from ziptag.printers import Material, Nozzle, Printer

STUDIO_VERSION = "02.09.01.70"
BODY_COLOR = "#1A1A1A"
TEXT_COLOR = "#FF6600"
BODY_EXTRUDER, TEXT_EXTRUDER = 1, 2      # filament slots: 1 = body, 2 = text
PLATE_GAP_RATIO = 0.2                    # Bambu Studio spaces plates by 20 % of the bed size

_NS = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
       'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
       'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p"')
_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
 <Default Extension="gcode" ContentType="text/x.gcode"/>
</Types>"""
_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""
_MODEL_REL_TYPE = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
_SLICE_INFO = f"""<?xml version="1.0" encoding="UTF-8"?>
<config>
  <header>
    <header_item key="X-BBL-Client-Type" value="slicer"/>
    <header_item key="X-BBL-Client-Version" value="{STUDIO_VERSION}"/>
  </header>
</config>"""


def load_settings(printer: Printer, material: Material) -> dict:
    """Load the pre-built Bambu Studio project settings for a printer/material pair."""
    path = resource_dir("templates") / f"{printer.key}_{material.value}.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def prime_tower_width(settings: dict) -> float:
    """Width of the prime tower the template asks for (mm)."""
    return float(settings.get("prime_tower_width", 35))


def plate_origin(index: int, count: int, printer: Printer) -> tuple[float, float]:
    """Where Bambu Studio puts plate ``index`` of ``count`` in its shared 3D scene."""
    cols = max(1, round(math.sqrt(count)))
    if math.sqrt(count) > cols:
        cols += 1
    row, col = divmod(index, cols)
    return (col * printer.bed_x * (1 + PLATE_GAP_RATIO),
            -row * printer.bed_y * (1 + PLATE_GAP_RATIO))


def apply_user_options(settings: dict, printer: Printer, nozzle: Nozzle, plate_count: int, tower: Rect) -> dict:
    """Patch a template for the chosen nozzle, colours and prime-tower position."""
    settings = dict(settings)
    settings["filament_colour"] = [BODY_COLOR, TEXT_COLOR]
    if printer.dual_nozzle:
        volume = "High Flow" if nozzle is Nozzle.HIGH_FLOW else "Standard"
        settings["nozzle_volume_type"] = [volume, volume]
        settings["extruder_nozzle_stats"] = [f"{volume}#1", f"{volume}#1"]
    settings["wipe_tower_x"] = [f"{tower.x0:g}"] * plate_count
    settings["wipe_tower_y"] = [f"{tower.y0:g}"] * plate_count
    settings["layer_height"] = f"{c.LAYER_BODY:g}"
    settings["initial_layer_print_height"] = f"{c.LAYER_BODY:g}"
    return settings


class _ProjectBuilder:
    """Collects the XML fragments of a Bambu project while tags are added plate by plate."""

    def __init__(self, printer: Printer, plate_count: int):
        self.printer = printer
        self.plate_count = plate_count
        self.object_files: dict[str, str] = {}
        self.rels: list[str] = []
        self.resources: list[str] = []
        self.build_items: list[str] = []
        self.object_config: list[str] = []
        self.plate_config: list[str] = []
        self.layer_ranges: list[str] = []
        self.cut_info: list[str] = []
        self._next_id = 1
        self._tag_no = 0

    def _take_id(self) -> int:
        self._next_id += 1
        return self._next_id - 1

    def add_plate(self, plate_no: int, plate: list[tuple[TagMesh, Placement]]) -> None:
        origin = plate_origin(plate_no, self.plate_count, self.printer)
        instances: list[str] = []
        for tag, place in plate:
            assembly_id = self._add_tag(tag, place, origin)
            instances += ["    <model_instance>", f'      <metadata key="object_id" value="{assembly_id}"/>',
                          '      <metadata key="instance_id" value="0"/>',
                          f'      <metadata key="identify_id" value="{100 + self._tag_no}"/>',
                          "    </model_instance>"]
        self.plate_config += ["  <plate>", f'    <metadata key="plater_id" value="{plate_no + 1}"/>',
                              '    <metadata key="plater_name" value=""/>',
                              '    <metadata key="locked" value="false"/>',
                              '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
                              '    <metadata key="gcode_file" value=""/>', *instances, "  </plate>"]

    def _add_tag(self, tag: TagMesh, place: Placement, origin: tuple[float, float]) -> int:
        """Add one tag (body + text parts as one object); returns the assembly object id."""
        self._tag_no += 1
        name = f"Tag{self._tag_no:02d}"
        parts = [("body", tag.body, BODY_EXTRUDER)]
        if tag.inlay is not None:
            parts.append(("text", tag.inlay, TEXT_EXTRUDER))

        volumes, part_config, components, faces = [], [], [], 0
        for volume_no, (part_name, solid, extruder) in enumerate(parts):
            mesh = to_mesh(solid)
            centre = tuple(float(v) for v in (mesh.vertices.min(axis=0) + mesh.vertices.max(axis=0)) / 2.0)
            part_id = self._take_id()
            volumes.append((part_id, MeshData(mesh.vertices - np.array(centre), mesh.triangles)))
            part_config += _part_config(part_id, f"{name}_{part_name}", extruder, volume_no, centre,
                                        len(mesh.triangles))
            components.append((part_id, centre))
            faces += len(mesh.triangles)

        assembly_id = self._take_id()
        obj_path = f"/3D/Objects/object_{self._tag_no}.model"
        self.object_files[obj_path.lstrip("/")] = _object_file(volumes)
        self.rels.append(f' <Relationship Target="{obj_path}" Id="rel-{self._tag_no}" Type="{_MODEL_REL_TYPE}"/>')
        self.resources += [f'  <object id="{assembly_id}" p:UUID="{new_uuid()}" type="model">', "   <components>"]
        self.resources += [f'    <component p:path="{obj_path}" objectid="{pid}" p:UUID="{new_uuid()}" '
                           f'transform="1 0 0 0 1 0 0 0 1 {ctr[0]:.6f} {ctr[1]:.6f} {ctr[2]:.6f}"/>'
                           for pid, ctr in components]
        self.resources += ["   </components>", "  </object>"]
        self.build_items.append(
            f'  <item objectid="{assembly_id}" p:UUID="{new_uuid()}" '
            f'transform="1 0 0 0 1 0 0 0 1 {origin[0] + place.x:.6f} {origin[1] + place.y:.6f} 0" printable="1"/>')
        label = xml_attr(tag.spec.text.strip() or name)
        self.object_config += [f'  <object id="{assembly_id}">', f'    <metadata key="name" value="{label}"/>',
                               f'    <metadata key="extruder" value="{BODY_EXTRUDER}"/>',
                               f'    <metadata face_count="{faces}"/>', *part_config, "  </object>"]
        self.cut_info += [f' <object id="{assembly_id}">',
                          '  <cut_id id="0" check_sum="1" connectors_cnt="0"/>', " </object>"]
        self.layer_ranges += [f' <object id="{self._tag_no}">',
                              f'  <range min_z="{c.Z_SWITCH}" max_z="{c.THICKNESS}">',
                              f'   <option opt_key="layer_height">{c.LAYER_TOP}</option>', "  </range>", " </object>"]
        return assembly_id

    # ---- documents -------------------------------------------------------------------
    def main_model(self, title: str) -> str:
        return "\n".join([
            '<?xml version="1.0" encoding="UTF-8"?>', f'<model unit="millimeter" xml:lang="en-US" {_NS}>',
            f' <metadata name="Application">BambuStudio-{STUDIO_VERSION}</metadata>',
            ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
            f' <metadata name="Title">{xml_attr(title)}</metadata>',
            f' <metadata name="Description">Created by Ziptie Tags {__version__}</metadata>',
            " <resources>", *self.resources, " </resources>", f' <build p:UUID="{new_uuid()}">',
            *self.build_items, " </build>", "</model>"])

    def model_settings(self) -> str:
        return "\n".join(['<?xml version="1.0" encoding="UTF-8"?>', "<config>", *self.object_config,
                          *self.plate_config, "  <assemble>", "  </assemble>", "</config>"])

    def model_rels(self) -> str:
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                + "\n".join(self.rels) + "\n</Relationships>")

    def write(self, path: Path, settings: dict, title: str) -> None:
        def objects(items: list[str]) -> str:
            return "\n".join(['<?xml version="1.0" encoding="utf-8"?>', "<objects>", *items, "</objects>"])

        sequence = {f"plate_{i + 1}": {"nozzle_sequence": [], "optimal_assignment": [], "sequence": []}
                    for i in range(self.plate_count)}
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", _CONTENT_TYPES)
            z.writestr("_rels/.rels", _ROOT_RELS)
            z.writestr("3D/3dmodel.model", self.main_model(title))
            z.writestr("3D/_rels/3dmodel.model.rels", self.model_rels())
            for name, text in self.object_files.items():
                z.writestr(name, text)
            z.writestr("Metadata/project_settings.config", json.dumps(settings, indent=4))
            z.writestr("Metadata/model_settings.config", self.model_settings())
            z.writestr("Metadata/layer_config_ranges.xml", objects(self.layer_ranges))
            z.writestr("Metadata/cut_information.xml", objects(self.cut_info))
            z.writestr("Metadata/slice_info.config", _SLICE_INFO)
            z.writestr("Metadata/filament_sequence.json", json.dumps(sequence))


def write_bambu_3mf(path: Path, plates: list[list[tuple[TagMesh, Placement]]], printer: Printer,
                    material: Material, nozzle: Nozzle, tower: Rect, title: str = "Ziptie Tags") -> None:
    """Write a Bambu Studio project holding every tag on its plate; ``tower`` is the prime-tower area."""
    settings = apply_user_options(load_settings(printer, material), printer, nozzle, len(plates), tower)
    builder = _ProjectBuilder(printer, len(plates))
    for plate_no, plate in enumerate(plates):
        builder.add_plate(plate_no, plate)
    builder.write(path, settings, title)


def _object_file(volumes: list[tuple[int, MeshData]]) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<model unit="millimeter" xml:lang="en-US" {_NS}>',
           ' <metadata name="BambuStudio:3mfVersion">1</metadata>', " <resources>"]
    for object_id, mesh in volumes:
        out += [f'  <object id="{object_id}" p:UUID="{new_uuid()}" type="model">', "   <mesh>", "    <vertices>",
                *vertices_xml(mesh, "     "), "    </vertices>", "    <triangles>",
                *triangles_xml(mesh, "     "), "    </triangles>", "   </mesh>", "  </object>"]
    return "\n".join([*out, " </resources>", "</model>"])


def _part_config(part_id: int, name: str, extruder: int, volume_no: int, centre: tuple[float, ...],
                 triangles: int) -> list[str]:
    matrix = f"1 0 0 {centre[0]!r} 0 1 0 {centre[1]!r} 0 0 1 {centre[2]!r} 0 0 0 1"
    return [f'    <part id="{part_id}" subtype="normal_part" uuid="{new_uuid()}">',
            f'      <metadata key="name" value="{name}"/>',
            f'      <metadata key="extruder" value="{extruder}"/>',
            f'      <metadata key="matrix" value="{matrix}"/>',
            f'      <metadata key="source_file" value="{name}.stl"/>',
            '      <metadata key="source_object_id" value="0"/>',
            f'      <metadata key="source_volume_id" value="{volume_no}"/>',
            f'      <metadata key="source_offset_x" value="{centre[0]!r}"/>',
            f'      <metadata key="source_offset_y" value="{centre[1]!r}"/>',
            f'      <metadata key="source_offset_z" value="{centre[2]!r}"/>',
            f'      <mesh_stat face_count="{triangles}" edges_fixed="0" degenerate_facets="0" '
            'facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
            "    </part>"]
