"""Priority 3 Phase A: GeometryBackend protocol (bpy-free)."""
from typing import get_args

from pro.geom_api import (
    DuplicateFacesResult,
    ExtrudeFaceResult,
    GeometryBackend,
    Vec3,
)
from pro.geometry import GeometryContext


def test_vec3_is_float_triple():
    v: Vec3 = (1.0, 2.0, 3.0)
    assert len(v) == 3


def test_extrude_duplicate_result_dataclasses():
    er = ExtrudeFaceResult(extruded_face="face-a", geom=("a", "b"))
    assert er.extruded_face == "face-a"
    dr = DuplicateFacesResult(faces=["f1"], geom=[])
    assert dr.faces == ["f1"]


def test_fake_backend_satisfies_protocol():
    class FakeBackend:
        def reverse_faces(self, faces):
            pass

        def extrude_face_region(self, face):
            return ExtrudeFaceResult(extruded_face=face)

        def translate_verts(self, verts, delta):
            pass

        def delete_faces(self, faces):
            pass

        def duplicate_faces(self, faces):
            return DuplicateFacesResult(faces=list(faces))

    backend = FakeBackend()
    assert isinstance(backend, GeometryBackend)


def test_geometry_context_api_requires_backend():
    geo = GeometryContext()
    try:
        _ = geo.api
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "backend" in str(e).lower()


def test_geometry_context_api_returns_attached_backend():
    class FakeBackend:
        def reverse_faces(self, faces):
            pass

        def extrude_face_region(self, face):
            return ExtrudeFaceResult(extruded_face=face)

        def translate_verts(self, verts, delta):
            pass

        def delete_faces(self, faces):
            pass

        def duplicate_faces(self, faces):
            return DuplicateFacesResult(faces=list(faces))

    geo = GeometryContext()
    backend = FakeBackend()
    geo.attach(bm=None, vertex_registry=None, backend=backend)
    assert geo.api is backend
