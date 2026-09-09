"""
Blender geometry / material backends (Phase 4 + Priority 3 Phase A).

Lifecycle (open/write/free) plus GeometryBackend mesh ops used by shape
grammar. pro.GeometryContext / MaterialContext / geom_api stay bpy-free.
"""
import bmesh

from pro.geom_api import DuplicateFacesResult, ExtrudeFaceResult

from .material import MaterialManager
from .util import VertexRegistry
from .join import JoinManager


class BlenderGeometryBackend:
    """
    Creates/owns a bmesh for one apply and implements GeometryBackend ops
    by wrapping bmesh.ops (moved out of shape.py / operators).
    """

    def __init__(self):
        self._bm = None
        self._owns_bm = False

    def open(self, mesh):
        """
        Build a bmesh from `mesh` and return it. Caller should attach it to
        GeometryContext; close() frees the bmesh.
        """
        bm = bmesh.new()
        bm.from_mesh(mesh)
        if hasattr(bm.faces, "ensure_lookup_table"):
            bm.faces.ensure_lookup_table()
        self._bm = bm
        self._owns_bm = True
        return bm

    def create_vertex_registry(self):
        return VertexRegistry()

    def join_manager_factory(self):
        return JoinManager

    def write_to_mesh(self, mesh):
        if self._bm is not None:
            self._bm.to_mesh(mesh)

    def close(self, geometry_context=None):
        if self._owns_bm and self._bm is not None:
            self._bm.free()
        self._bm = None
        self._owns_bm = False

    # --- GeometryBackend -------------------------------------------------

    def _require_bm(self):
        if self._bm is None:
            raise RuntimeError("BlenderGeometryBackend has no open bmesh")
        return self._bm

    def reverse_faces(self, faces):
        bm = self._require_bm()
        bmesh.ops.reverse_faces(bm, faces=list(faces))

    def extrude_face_region(self, face):
        bm = self._require_bm()
        geom = bmesh.ops.extrude_face_region(bm, geom=(face,))
        extruded = None
        for item in geom["geom"]:
            if isinstance(item, bmesh.types.BMFace):
                extruded = item
                break
        if extruded is None:
            raise RuntimeError("extrude_face_region produced no face")
        return ExtrudeFaceResult(extruded_face=extruded, geom=geom["geom"])

    def translate_verts(self, verts, delta):
        bm = self._require_bm()
        bmesh.ops.translate(bm, verts=list(verts), vec=delta)

    def delete_faces(self, faces):
        bm = self._require_bm()
        bmesh.ops.delete(bm, geom=list(faces), context="FACES")

    def duplicate_faces(self, faces):
        bm = self._require_bm()
        duplicate = bmesh.ops.duplicate(bm, geom=list(faces))
        new_faces = [
            g for g in duplicate["geom"] if isinstance(g, bmesh.types.BMFace)
        ]
        return DuplicateFacesResult(faces=new_faces, geom=duplicate["geom"])


class BlenderMaterialBackend:
    """Creates a MaterialManager bound to the active Blender object/scene."""

    def __init__(self, blender_context=None):
        self._blender_context = blender_context

    def create_material_manager(self):
        return MaterialManager()

    def render_engine(self):
        bc = self._blender_context
        if bc is None:
            return None
        scene = getattr(bc, "scene", None)
        if scene is None:
            return None
        return scene.render.engine

    def close(self, material_context=None):
        pass


def attach_blender_backends(ctx, mesh, blender_context=None):
    """
    Attach Blender geometry + material backends to ctx for one apply.

    Returns (bm, geo_backend) so apply can write/free consistently.
    """
    if blender_context is None:
        blender_context = getattr(ctx, "blenderContext", None)

    geo_backend = BlenderGeometryBackend()
    mat_backend = BlenderMaterialBackend(blender_context)

    bm = geo_backend.open(mesh)
    ctx.geometry.attach(
        bm=bm,
        vertex_registry=geo_backend.create_vertex_registry(),
        faces_for_removal=[],
        join_manager_factory=geo_backend.join_manager_factory(),
        backend=geo_backend,
    )
    ctx.materials.attach(
        manager=mat_backend.create_material_manager(),
        backend=mat_backend,
    )
    return bm, geo_backend
