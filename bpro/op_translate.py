import mathutils
import pro
from pro import context
from pro.rule_context import resolve_rule_context
from .shape import Shape2d, rotation_zNormal_xHorizontal


class Translate(pro.op_translate.Translate):
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        shape = ctx.getState().shape
        # only 2D shapes can be translated at the moment!
        if not isinstance(shape, Shape2d):
            return
        # rotation matrix, note True as the third parameter to rotation_zNormal_xHorizontal(..)
        matrix = rotation_zNormal_xHorizontal(shape.firstLoop, shape.getNormal(), True)
        delta = matrix @ mathutils.Vector(self.vec)
        ctx.geometry.api.translate_verts(shape.face.verts, delta)
