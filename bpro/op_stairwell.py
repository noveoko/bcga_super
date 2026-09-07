import pro
from pro import context
from pro.stairs import stair_profile

from .shape import Rectangle


class _DeleteFace:
    """Drops extrude2's closing face without going through Operator.__init__."""

    def execute(self):
        context.getState().shape.delete()


class Stairwell(pro.op_stairwell.Stairwell):
    def execute(self):
        shape = context.getState().shape
        if not isinstance(shape, Rectangle):
            return
        w, h = shape.size()
        axis = self.axis
        if axis is None:
            axis = pro.x if w >= h else pro.y
            self.axis = axis
        run_available = w if axis == pro.x else h
        profile = stair_profile(self.rise, self.tread, self.riser, run_available)
        self.parts = profile["parts"]
        if self.last is None:
            self.last = _DeleteFace()
        shapesWithRule = shape.extrude2(self.parts, self)
        for entry in shapesWithRule:
            context.pushState(shape=entry[0])
            entry[1].execute()
            context.popState()
