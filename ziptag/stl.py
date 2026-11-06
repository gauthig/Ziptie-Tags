"""Binary STL writer (geometry only: no colours, plates or slicer settings)."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from manifold3d import Manifold

from ziptag.geometry import TagMesh
from ziptag.layout import Placement
from ziptag.mesh import to_mesh

PLATE_SPACING = 50.0   # gap between plate groups laid out side by side along X


def tag_solid(tag: TagMesh) -> Manifold:
    """Body and text inlay fused into one solid (STL cannot carry two colours)."""
    return tag.body if tag.inlay is None else tag.body + tag.inlay


def write_stl(path: Path, plates: list[list[tuple[TagMesh, Placement]]], bed_x: float) -> None:
    """Write every tag, in plate layout positions, into one binary STL."""
    chunks = []
    for plate_no, plate in enumerate(plates):
        x_offset = plate_no * (bed_x + PLATE_SPACING)
        for tag, place in plate:
            mesh = to_mesh(tag_solid(tag))
            shift = np.array([place.x + x_offset, place.y, 0.0])
            chunks.append((mesh.vertices + shift)[mesh.triangles])        # (m, 3, 3)
    tris = np.concatenate(chunks)
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)
    record = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])
    record["n"], record["v"] = normals, tris
    with open(path, "wb") as fh:
        fh.write(b"Ziptie Tags binary STL".ljust(80, b" "))
        fh.write(struct.pack("<I", len(tris)))
        fh.write(record.tobytes())
