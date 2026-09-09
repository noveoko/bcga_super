import pro
from pro import context
from pro.rule_context import resolve_rule_context
from .polygon import Polygon
from .polygon_manager import Manager
from .op_delete import Delete

class Inset(pro.op_inset.Inset):
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        shape = ctx.getState().shape
        face = shape.face
        manager = Manager()
        polygon = Polygon(face.verts, shape.getNormal(), manager)
        manager.rule = self.side
        kwargs = {"height": self.height} if self.height else {}
        polygon.inset(*self.insets, **kwargs)
        # create a shape for the cap if necessary
        cap = self.cap
        if not isinstance(cap, Delete):
            shape = polygon.getShape(type(shape))
            if cap:
                ctx.pushState(shape=shape)
                self.cap.execute(ctx)
                ctx.popState()
        if not self.keepOriginal:
            ctx.facesForRemoval.append(face)
        # finalizing: if there is a rule for the shape, execute it
        for entry in manager.shapes:
            ctx.pushState(shape=entry[0])
            entry[1].execute(ctx)
            ctx.popState()