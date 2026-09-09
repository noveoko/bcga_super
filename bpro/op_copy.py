import pro
from pro import context
from pro.rule_context import resolve_rule_context
from .shape import Shape2d


class Copy(pro.op_copy.Copy):
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        shape = ctx.getState().shape
        # only 2D shapes can be copied at the moment!
        if not isinstance(shape, Shape2d):
            return

        result = ctx.geometry.api.duplicate_faces((shape.face,))
        if not result.faces:
            return
        copiedFace = result.faces[0]
        constructor = type(shape)
        copiedShape = constructor(copiedFace.loops[0])

        if self.operator:
            ctx.pushState(shape=copiedShape)
            self.operator.execute(ctx)
            ctx.popState()
