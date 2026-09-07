import importlib.util
import os
import sys
import inspect
import bpy
import bmesh

from pro import context

from .material import MaterialManager

from .util import VertexRegistry

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

from .join import JoinManager


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


def apply(ruleFile, startRule="Begin", trace=False):
    """
    Args:
        trace (bool): when True, a full resolved JSON-serializable trace of
            everything the rule tree actually did for this specific
            generated building is made available afterwards as
            context.buildingTrace (a dict; see pro.base.Rule.to_dict()).
            Does not change this function's return value, so existing
            callers doing `module, params = bpro.apply(...)` keep working
            unchanged. False by default: zero extra overhead when unused.
    """
    from .bl_util import create_rectangle

    blenderContext = context.blenderContext
    obj = blenderContext.object
    if obj:
        bpy.ops.object.mode_set(mode="OBJECT")

    noMeshCondition = not obj or obj.type != "MESH"
    if noMeshCondition or len(obj.data.polygons) != 1:
        if not noMeshCondition:
            # delete if it's non-flat mesh
            bpy.ops.object.delete()
        create_rectangle(blenderContext, 20, 10)
    # apply all transformations to the active Blender object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # setting the path to the rule for context
    context.ruleFile = ruleFile if isinstance(
        ruleFile, str) else ruleFile.__file__
    params = None
    mesh = blenderContext.object.data
    # create a uv layer for the mesh
    # TODO: a separate pass through the rules is needed to find out how many uv layers are needed
    mesh.uv_layers.new(name=Texture.defaultLayer)
    # initialize the context
    context.init()
    # initializing bmesh instance
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if hasattr(bm.faces, "ensure_lookup_table"):
        bm.faces.ensure_lookup_table()
    context.addAttribute("bm", bm)
    # list of unused faces for removal
    context.addAttribute("facesForRemoval", [])
    # set up the material registry
    context.addAttribute("materialManager", MaterialManager())
    # set up vertex registry to ensure vertex uniqueness
    context.addAttribute("vertexRegistry", VertexRegistry())
    # set a constructor for join manager, it may be replaced by actual instance of the join manager
    context.addAttribute("joinManager", JoinManager)

    # push the initial state with the initial shape to the execution stack
    context.pushState(shape=getInitialShape(bm))

    if isinstance(ruleFile, str):
        module = getModule(ruleFile)

        # prepare context internal stuff
        context.prepare()
        # params is a list of tuples: (paramName, instanceofParamClass)
        params = getParams(module)
    else:
        # ruleFile is actually a module
        module = ruleFile

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

    # write everything back to the mesh
    bm.to_mesh(mesh)
    # cleaning context from blender specific members
    context.removeAttributes()

    return (module, params)


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
