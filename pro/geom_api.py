"""
GeometryBackend protocol (Priority 3 / Phase A).

bpy-free. Blender implements this in bpro.backends.BlenderGeometryBackend;
a MemoryGeometryBackend (Phase B) will implement the same surface for pytest.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence, runtime_checkable

# Opaque mesh element handles (BMFace/BMVert on Blender; ints/objects on Memory).
FaceRef = Any
VertRef = Any
Vec3 = tuple[float, float, float]


@dataclass
class ExtrudeFaceResult:
    """Result of extruding a single face region."""

    extruded_face: FaceRef
    # Raw geom list from the backend (Blender returns mixed BMVert/BMEdge/BMFace).
    geom: Sequence[Any] = ()


@dataclass
class DuplicateFacesResult:
    faces: Sequence[FaceRef]
    geom: Sequence[Any] = ()


@runtime_checkable
class GeometryBackend(Protocol):
    """
    Mesh mutation API used by shape grammar / operators.

    Phase A covers the ops currently inlined as bmesh.ops in shape.py /
    op_translate / op_copy. Additional methods land as operators migrate.
    """

    def reverse_faces(self, faces: Sequence[FaceRef]) -> None:
        """Flip face winding / normals for the given faces."""

    def extrude_face_region(self, face: FaceRef) -> ExtrudeFaceResult:
        """Extrude a face region; returns the new cap face."""

    def translate_verts(self, verts: Sequence[VertRef], delta: Any) -> None:
        """Translate verts by delta (Vec3 or backend-native vector)."""

    def delete_faces(self, faces: Sequence[FaceRef]) -> None:
        """Delete faces from the mesh immediately."""

    def duplicate_faces(self, faces: Sequence[FaceRef]) -> DuplicateFacesResult:
        """Duplicate faces; returns the new face(s)."""
