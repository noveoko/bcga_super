import importlib.util
import os
import sys
import inspect
import bpy

from pro import context

from .op_decompose import Decompose
from .op_split import Split
from .op_extrude import Extrude
from .op_extrude2 import Extrude2
from .op_color import Color
from .op_material import Material
from .op_texture import Texture
from .op_delete import Delete
from .op_join import Join
from .op_inset import Inset
from .op_inset2 import Inset2
from .op_rectangle import Rectangle
from .op_hip_roof import HipRoof
from .op_gable_roof import GableRoof
from .op_round_corners import RoundCorners
import pro.op_chance
import pro.op_switch
from .op_copy import Copy
from .op_translate import Translate
from .op_partition import Partition
from .op_stairwell import Stairwell
from .op_openings import Openings

from pro.base import Param

from .shape import getInitialShape


def buildFactory():
    factory = context.factory
    factory["Decompose"] = Decompose
    factory["Split"] = Split
    factory["Extrude"] = Extrude
    factory["Extrude2"] = Extrude2
    factory["Color"] = Color
    factory["Material"] = Material
    factory["Texture"] = Texture
    factory["Delete"] = Delete
    factory["Join"] = Join
    factory["Inset"] = Inset
    factory["Inset2"] = Inset2
    factory["Rectangle"] = Rectangle
    factory["HipRoof"] = HipRoof
    factory["GableRoof"] = GableRoof
    factory["RoundCorners"] = RoundCorners
    factory["Chance"] = pro.op_chance.Chance
    factory["Switch"] = pro.op_switch.Switch
    factory["Copy"] = Copy
    factory["Translate"] = Translate
    factory["Partition"] = Partition
    factory["Stairwell"] = Stairwell
    factory["Openings"] = Openings


def apply(ruleFile, startRule="Begin", trace=False, session=None):
    """
    Args:
        trace (bool): when True, a full resolved JSON-serializable trace of
            everything the rule tree actually did for this specific
            generated building is made available afterwards as
            context.buildingTrace (a dict; see pro.base.Rule.to_dict()).
            Does not change this function's return value, so existing
            callers doing `module, params = bpro.apply(...)` keep working
            unchanged. False by default: zero extra overhead when unused.
        session: optional GenerationSession. When provided (or already active
            via `with GenerationSession()`), the module-level `pro.context`
            proxy forwards to that session's Context for the apply.
    """
    from pro.session import get_active_session

    # Activate the given session only if it is not already the active one
    # (so a `with GenerationSession()` batch does not flap ContextVar).
    activated_here = False
    if session is not None and get_active_session() is not session:
        session.activate()
        activated_here = True

    try:
        return _apply_inner(ruleFile, startRule=startRule, trace=trace)
    finally:
        if activated_here:
            session.deactivate()


def _apply_inner(ruleFile, startRule="Begin", trace=False):
    from .bl_util import create_rectangle

    blenderContext = context.blenderContext
    if blenderContext is None:
        raise RuntimeError(
            "bpro.apply requires context.blenderContext (set it on a "
            "GenerationSession or assign context.blenderContext = bpy.context)"
        )
    obj = blenderContext.object
    if obj:
        bpy.ops.object.mode_set(mode="OBJECT")

    noMeshCondition = not obj or obj.type != "MESH"
    if noMeshCondition or len(obj.data.polygons) != 1:
        if not noMeshCondition:
            # delete if it's non-flat mesh
            bpy.ops.object.delete()
        create_rectangle(blenderContext, 20, 10)
    # Bake location/rotation/scale into the mesh so rule execution (and
    # door/light records derived from bmesh verts) are in world space.
    # transform_apply only affects *selected* objects in Blender 5.x -- the
    # footprint is often active-but-unselected after create_footprint_from_points
    # deselects everything, which previously left obj.location at the plot
    # centroid while door/light children were spawned at local coords near
    # the origin (the "everything clumped in the rynek" bug).
    obj = blenderContext.object
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # setting the path to the rule for context
    context.ruleFile = ruleFile if isinstance(
        ruleFile, str) else ruleFile.__file__
    params = None
    mesh = blenderContext.object.data
    # create a uv layer for the mesh
    # TODO: a separate pass through the rules is needed to find out how many uv layers are needed
    mesh.uv_layers.new(name=Texture.defaultLayer)

    context.begin_apply()
    bm = None
    geo_backend = None
    try:
        # Phase 4: Blender backends own bmesh / MaterialManager construction.
        from .backends import attach_blender_backends
        bm, geo_backend = attach_blender_backends(
            context, mesh, blender_context=blenderContext
        )

        # push the initial state with the initial shape to the execution stack
        context.pushState(shape=getInitialShape(bm))

        if isinstance(ruleFile, str):
            # Re-executes the rule file; module-level param() calls re-register
            # into context.params (cleared by begin_apply).
            module = getModule(ruleFile)
        else:
            # ruleFile is already a module (addon re-apply path): no re-import,
            # so re-bind context.params from the module's Param instances.
            module = ruleFile
        params = getParams(module)
        context.params = [p for _name, p in params]
        # Always resolve random params for this apply (string and module paths).
        context.prepare()
        # setting the current operator to a dummy one to avoid an exception
        class dummy:
            def addChildOperator(self, o): pass

            def removeChildOperators(self, numParts): pass
        context.operator = dummy()
        # evaluate the rule set
        context.tracing = bool(trace)
        rootRule = getattr(module, startRule)()
        rootRule.execute()
        context.buildingTrace = rootRule.to_dict() if trace else None

        # remove unused faces from context.facesForRemoval
        bmesh.ops.delete(bm, geom=context.facesForRemoval, context='FACES')
        # there still may be some doubles, inspite of the use of util.VertexMaterial
        #bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)

        # clean up context.facesForRemoval
        context.facesForRemoval = []
        context.executeDeferred()
        # remove unused faces from context.facesForRemoval
        bmesh.ops.delete(bm, geom=context.facesForRemoval, context='FACES')

        # write everything back to the mesh (backend still owns bm until end_apply)
        if geo_backend is not None:
            geo_backend.write_to_mesh(mesh)
        else:
            bm.to_mesh(mesh)
        records = getattr(context, "ceilingLights", None) or []
        if records:
            from .lights import spawn_ceiling_lights
            spawn_ceiling_lights(records, parent=blenderContext.object)
            context.allCeilingLights.extend(records)
        doorRecords = getattr(context, "gameDoors", None) or []
        if doorRecords:
            from .doors import spawn_door_leaves
            spawned = spawn_door_leaves(doorRecords, parent=blenderContext.object)
            context.allGameDoors.extend(spawned)
        return (module, params)
    finally:
        # geometry.close() (via end_apply) frees the bmesh through the backend
        context.end_apply()


def isParam(member):
    """A predicate for the inspect.getmembers call"""
    return isinstance(member, Param)


def getModule(ruleFile):
    """Returns Python module object given a path to the rule file"""
    # remove extension from ruleFile if it was provided, then add it back
    # explicitly so we always resolve to a concrete .py file on disk
    ruleFile = os.path.splitext(ruleFile)[0] + ".py"
    moduleName = os.path.basename(ruleFile)[:-3]

    spec = importlib.util.spec_from_file_location(moduleName, ruleFile)
    if spec is None or spec.loader is None:
        raise ImportError("Could not load BCGA rule file '%s'" % ruleFile)
    module = importlib.util.module_from_spec(spec)
    # register in sys.modules so relative imports / reload() behave normally
    sys.modules[moduleName] = module
    spec.loader.exec_module(module)
    return module


def getParams(module):
    """Returns a list of tuples: (paramName, instanceofParamClass)"""
    return [m for m in inspect.getmembers(module, isParam)]


buildFactory()
