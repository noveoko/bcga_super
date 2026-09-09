import pro
from pro import context
from pro.rule_context import resolve_rule_context
from pro.base import Operator
from .polygon import Polygon
from .polygon_manager import Manager
from .op_delete import Delete

class Inset2(pro.op_inset2.Inset2):
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        shape = ctx.getState().shape
        face = shape.face
        manager = Manager()
        polygon = Polygon(face.verts, shape.getNormal(), manager)
        
        # process each inset
        for inset in self.insets:
            if isinstance(inset, tuple):
                height = inset[1]
                if isinstance(height, Operator):
                    rule = height
                    height = height.value
                else:
                    rule = self.side
                manager.rule = rule
                if float(inset[0]): # not zero
                    kwargs = {"height": height} if height else {}
                    polygon.inset(inset[0], **kwargs)
                else:
                    polygon.translate(height)
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