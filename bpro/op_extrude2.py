import pro
from pro import context
from pro.rule_context import resolve_rule_context

class Extrude2(pro.op_extrude2.Extrude2):
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        shape = ctx.getState().shape
        # We now know the absolute shape size, so let's update self.parts
        # for self.symmetric = True and self.relativeCoord1 = False
        if self.symmetric and not self.relativeCoord1:
            self.updateSymmetricAbsolute(shape)
        shapesWithRule = shape.extrude2(self.parts, self)
        # apply the rule for each shape in shapesWithRule list
        for entry in shapesWithRule:
            ctx.pushState(shape=entry[0])
            entry[1].execute(ctx)
            ctx.popState()
    
    def updateSymmetricAbsolute(self, shape):
        # Update self.parts for self.symmetric = True and self.relativeCoord1 = False
        parts = self.parts
        argIndex = len(parts)-1
        # find size along axis 1:
        size = shape.size()[0 if self.axis == pro.x else 1]
        # Treat the special case when there is no segment crossing size/2 and parallel to the reference axis
        if parts[-1][0]!=size/2:
            # add the middle part
            part = parts[-1]
            parts.append( (size-part[0], part[1]) )
        while argIndex>0:
            argIndex -= 1
            part = parts[argIndex]
            prevPart = parts[argIndex+1]
            coord1 = size-part[0]
            part = (coord1, part[1]) if len(prevPart)==2 else (coord1, part[1], prevPart[2])
            parts.append(part)
