from pro.base import Operator
from pro import context
from pro.rule_context import resolve_rule_context

class Delete(Operator):
    
    def __init__(self):
        super().__init__()
    
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        shape = ctx.getState().shape
        shape.delete()