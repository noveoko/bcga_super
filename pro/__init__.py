from .op_split import split

from .op_decompose import decompose
from .op_decompose import front, back, left, right, top, bottom, side, all

from .op_extrude import extrude

from .op_extrude2 import extrude2
from .op_extrude2 import middle, section, cap1, cap2, cap

from .op_color import color
from .op_material import material
from .op_texture import texture
from .op_delete import delete
from .op_join import join
from .op_inset import inset
from .op_inset2 import inset2

from .op_rectangle import rectangle

from .op_hip_roof import hip_roof
from .op_gable_roof import gable_roof
from .op_round_corners import round_corners
from .op_chance import chance
from .op_switch import switch
from .base import choice

from .op_copy import copy

from .op_translate import translate

from .base import flt, rel
from .base import shape
from .base import param, random
from .base import context
from .base import Rule

x = "x"
y = "y"
z = "z"

face = "face"  # hip_roof
soffit = "soffit"  # hip_roof
fascia = "fascia"  # hip_roof

original = "original"
last = "last"


def rule(operator):
    def inner(*args, **kwargs):
        return Rule(operator, args, kwargs)
    return inner


def repeat(*args):
    return args


def getMetadata(module):
    """
    Reads optional rule-file metadata, following a simple convention: a
    rule file may declare any of these module-level variables (nothing is
    required -- rule files that don't use this convention just get empty
    strings/lists back):

        __version__ = "1.2.0"
        __author__ = "Jane Doe"
        __description__ = "A four-story office building with a central atrium"
        __tags__ = ["commercial", "office", "modern"]

    Returns a dict with keys "version", "author", "description", "tags"
    (tags is always a list; the others are always strings). This is a
    plain-data convention only, with nothing to register or enforce, so
    any rule file can adopt it just by adding the variables above -- and
    it has no bpy dependency, so it's usable from generate.py/bcga_tui.py
    without launching Blender.
    """
    return {
        "version": getattr(module, "__version__", "") or "",
        "author": getattr(module, "__author__", "") or "",
        "description": getattr(module, "__description__", "") or "",
        "tags": list(getattr(module, "__tags__", None) or []),
    }
