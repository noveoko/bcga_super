import pro
from pro import context
from pro.rule_context import resolve_rule_context

class Join(pro.op_join.Join):
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        shape = ctx.getState().shape
        ctx.addDeferred(shape, self)
    
    def resolve(self, deferred):
        ctx = resolve_rule_context()
        ctx.joinManager.process(deferred)
