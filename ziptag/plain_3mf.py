"""Plain (slicer-neutral) 3MF writer: geometry and two named colours, no vendor metadata."""
from __future__ import annotations

import zipfile
from pathlib import Path

from ziptag import __version__
from ziptag.geometry import TagMesh
from ziptag.layout import Placement
from ziptag.mesh import to_mesh, triangles_xml, vertices_xml, xml_attr

BODY_COLOR = "#1A1A1A"
TEXT_COLOR = "#FF6600"
PLATE_SPACING = 50.0   # gap between plate groups laid out side by side

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""


def write_plain_3mf(path: Path, plates: list[list[tuple[TagMesh, Placement]]],
                    bed_x: float, title: str = "Ziptie Tags") -> None:
    """Write all tags into one 3MF; plates are placed side by side along X."""
    resources = [
        ' <basematerials id="1">',
        f'  <base name="Tag body" displaycolor="{BODY_COLOR}"/>',
        f'  <base name="Tag text" displaycolor="{TEXT_COLOR}"/>',
        ' </basematerials>',
    ]
    items: list[str] = []
    next_id = 2
    for plate_no, plate in enumerate(plates):
        x_offset = plate_no * (bed_x + PLATE_SPACING)
        for tag, place in plate:
            parts = [("body", tag.body, 0)]
            if tag.inlay is not None:
                parts.append(("text", tag.inlay, 1))
            comp_ids = []
            for _, solid, material in parts:
                mesh = to_mesh(solid)
                resources += [f' <object id="{next_id}" type="model" pid="1" pindex="{material}">', '  <mesh>',
                              '   <vertices>', *vertices_xml(mesh, "    "), '   </vertices>',
                              '   <triangles>', *triangles_xml(mesh, "    "), '   </triangles>',
                              '  </mesh>', ' </object>']
                comp_ids.append(next_id)
                next_id += 1
            name = xml_attr(tag.spec.text.strip() or "tag")
            resources += [f' <object id="{next_id}" type="model" name="{name}">', '  <components>',
                          *[f'   <component objectid="{cid}"/>' for cid in comp_ids],
                          '  </components>', ' </object>']
            items.append(f'  <item objectid="{next_id}" transform="1 0 0 0 1 0 0 0 1 '
                         f'{place.x + x_offset:.4f} {place.y:.4f} 0"/>')
            next_id += 1

    model = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
             f' <metadata name="Title">{xml_attr(title)}</metadata>',
             f' <metadata name="Application">Ziptie Tags {__version__}</metadata>',
             ' <resources>', *resources, ' </resources>', ' <build>', *items, ' </build>', '</model>']
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("3D/3dmodel.model", "\n".join(model))
