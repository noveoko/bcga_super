"""Phase 4: GeometryContext / MaterialContext + join manager factory."""
import pytest

from pro import context, GeometryContext, MaterialContext
from pro.geometry import GeometryContext as GeoCls
from pro.material_context import MaterialContext as MatCls


def test_context_exposes_geometry_and_materials_subcontexts():
    assert isinstance(context.geometry, GeometryContext)
    assert isinstance(context.materials, MaterialContext)


def test_geometry_aliases_route_through_subcontext():
    context.begin_apply()
    sentinel_bm = object()
    sentinel_vr = object()
    context.bm = sentinel_bm
    context.vertexRegistry = sentinel_vr
    context.facesForRemoval = ["face"]
    assert context.geometry.bm is sentinel_bm
    assert context.geometry.vertexRegistry is sentinel_vr
    assert context.geometry.facesForRemoval == ["face"]
    context.end_apply()
    assert context.bm is None
    assert context.vertexRegistry is None
    assert context.facesForRemoval == []


def test_material_manager_alias():
    context.begin_apply()
    mgr = object()
    context.materialManager = mgr
    assert context.materials.manager is mgr
    assert context.materialManager is mgr
    context.end_apply()
    assert context.materialManager is None


def test_create_join_manager_instantiates_factory_once():
    class FakeJoin:
        def __init__(self):
            self.finalized = False

        def finalize(self):
            self.finalized = True

    geo = GeometryContext()
    geo.attach(bm=None, vertex_registry=None, join_manager_factory=FakeJoin)
    jm1 = geo.create_join_manager()
    jm2 = geo.create_join_manager()
    assert isinstance(jm1, FakeJoin)
    assert jm1 is jm2  # cached instance


def test_create_join_manager_requires_factory():
    geo = GeometryContext()
    with pytest.raises(RuntimeError, match="join_manager_factory"):
        geo.create_join_manager()


def test_execute_deferred_uses_geometry_join_manager():
    class FakeJoin:
        def __init__(self):
            self.processed = []
            self.finalized = False

        def process(self, deferred):
            self.processed.append(deferred)

        def finalize(self):
            self.finalized = True

    class FakeOp:
        def resolve(self, deferred):
            context.joinManager.process(deferred)

    context.begin_apply()
    context.geometry.attach(
        bm=None, vertex_registry=None, join_manager_factory=FakeJoin
    )
    shape = object()
    op = FakeOp()
    context.addDeferred(shape, op)
    context.executeDeferred()
    jm = context.joinManager
    assert isinstance(jm, FakeJoin)
    assert jm.processed == [(shape, op)]
    assert jm.finalized is True
    context.end_apply()


def test_geometry_material_are_bpy_free_modules():
    # Importing these must not require bpy.
    import pro.geometry as g
    import pro.material_context as m
    assert g.GeometryContext is GeoCls
    assert m.MaterialContext is MatCls
