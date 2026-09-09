import pro
from pro import context
from pro.rule_context import resolve_rule_context

def decompose_execute(shape, _parts, ctx=None):
	ctx = resolve_rule_context(ctx)
	# create a dict from the operatorDef list
	parts = {}
	for part in _parts:
		parts[part.value] = part
	
	# components is a dictionary with a comp-selector as the key and a list of 2D-shapes as the related value 
	components = shape.decompose(parts)
	if len(components)>0:
		# now apply the rule for each decomposed 2D-shape
		for selector in components:
			for _shape in components[selector]:
				ctx.pushState(shape=_shape)
				parts[selector].execute(ctx)
				ctx.popState()


class Decompose(pro.op_decompose.Decompose):
	
	def execute(self, ctx=None):
		ctx = resolve_rule_context(ctx)
		decompose_execute(ctx.getState().shape, self.parts, ctx)
