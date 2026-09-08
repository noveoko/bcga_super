import mathutils
import pro
from pro import context
from .util import xAxis, yAxis
from .shape import createRectangle, rotation_zNormal_xHorizontal

class Rectangle(pro.op_rectangle.Rectangle):
    def execute(self):
        bm = context.bm
        state = context.getState()
        shape = state.shape
        # get rectangle origin
        origin = shape.center()
        xVec = self.xSize/2 * xAxis
        yVec = self.ySize/2 * yAxis
        matrix = rotation_zNormal_xHorizontal(shape.firstLoop, shape.getNormal(), True)

        if self.replace:
            context.popState()
            shape.delete()

        shape = createRectangle((
            bm.verts.new(matrix @ (-xVec - yVec) + origin),
            bm.verts.new(matrix @ (xVec - yVec) + origin),
            bm.verts.new(matrix @ (xVec + yVec) + origin),
            bm.verts.new(matrix @ (-xVec + yVec) + origin),
        ))
        if self.operator:
            context.pushState(shape=shape)
            self.operator.execute()
            context.popState()
        elif self.replace:
            context.pushState(shape=shape)