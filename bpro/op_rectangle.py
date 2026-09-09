import mathutils
import pro
from pro import context
from pro.rule_context import resolve_rule_context
from .util import xAxis, yAxis
from .shape import createRectangle, rotation_zNormal_xHorizontal

class Rectangle(pro.op_rectangle.Rectangle):
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        bm = ctx.bm
        state = ctx.getState()
        shape = state.shape
        # get rectangle origin
        origin = shape.center()
        xVec = self.xSize/2 * xAxis
        yVec = self.ySize/2 * yAxis
        matrix = rotation_zNormal_xHorizontal(shape.firstLoop, shape.getNormal(), True)

        if self.replace:
            ctx.popState()
            shape.delete()

        shape = createRectangle((
            bm.verts.new(matrix @ (-xVec - yVec) + origin),
            bm.verts.new(matrix @ (xVec - yVec) + origin),
            bm.verts.new(matrix @ (xVec + yVec) + origin),
            bm.verts.new(matrix @ (-xVec + yVec) + origin),
        ))
        if self.operator:
            ctx.pushState(shape=shape)
            self.operator.execute(ctx)
            ctx.popState()
        elif self.replace:
            ctx.pushState(shape=shape)