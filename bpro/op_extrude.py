import pro
from pro import context
from pro.rule_context import resolve_rule_context
from .op_decompose import decompose_execute

class Extrude(pro.op_extrude.Extrude):
	def execute(self, ctx=None):
		ctx = resolve_rule_context(ctx)
		state = ctx.getState()
		shape = state.shape.extrude(self)
		if self.parts:
			decompose_execute(shape, self.parts, ctx)
		else:
			state.shape = shape
	
	def execute_join(self, band, ctx=None):
		ctx = resolve_rule_context(ctx)
		band.extrude()