from ..rule_context import resolve_rule_context


def shape():
	"""Returns the current (top) shape from the stack"""
	ctx = resolve_rule_context()
	ctx.operator.executeChildOperators(ctx)
	return ctx.getState().shape
