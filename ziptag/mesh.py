"""Mesh helpers shared by the 3MF writers."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import numpy as np
from manifold3d import Manifold


@dataclass(frozen=True)
class MeshData:
    vertices: np.ndarray   # (n, 3) float
    triangles: np.ndarray  # (m, 3) int


def to_mesh(solid: Manifold) -> MeshData:
    """Extract vertex/triangle arrays from a manifold solid."""
    mesh = solid.to_mesh()
    return MeshData(np.asarray(mesh.vert_properties, dtype=float)[:, :3],
                    np.asarray(mesh.tri_verts, dtype=int))


def vertices_xml(mesh: MeshData, indent: str) -> list[str]:
    return [f'{indent}<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in mesh.vertices]


def triangles_xml(mesh: MeshData, indent: str) -> list[str]:
    return [f'{indent}<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh.triangles]


def xml_attr(text: str) -> str:
    """Escape text for use inside an XML attribute or element."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def new_uuid() -> str:
    return str(uuid.uuid4())
