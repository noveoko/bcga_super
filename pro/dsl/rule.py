from .operator import ComplexOperator, countOperator
from ..rule_context import (
	call_execute,
	push_rule_context,
	reset_rule_context,
	resolve_rule_context,
)
from ..serialization.trace import encode_value


class Rule(ComplexOperator):
	
	def __init__(self, operator, args, kwargs):
		self.operator = operator
		self.args = args
		self.kwargs = kwargs
		# count how many BCGA operators we have in args and kwargs
		numParts = 0
		for arg in args:
			if countOperator(arg):
				numParts += 1
		for k in kwargs:
			if countOperator(kwargs[k]):
				numParts += 1
		# list of child operators
		self.operators = []
		super().__init__(numParts)
	
	def execute(self, ctx=None):
		ctx = resolve_rule_context(ctx)
		token = push_rule_context(ctx)
		try:
			# setting the current operator to self
			ctx.operator = self
			self.operator(*self.args, **self.kwargs)
			self.executeChildOperators(ctx)
		finally:
			reset_rule_context(token)

	def addChildOperator(self, operator):
		"""Adds child operator"""
		self.operators.append(operator)
	
	def removeChildOperators(self, numOperators):
		while numOperators:
			self.operators.pop()
			numOperators -= 1
	
	def executeChildOperators(self, ctx=None):
		ctx = resolve_rule_context(ctx)
		# execute operators inside the body of the current operator
		tracing = ctx.tracing
		trace = [] if tracing else None
		for o in self.operators:
			call_execute(o, ctx)
			if tracing:
				trace.append(o.to_dict())
		if tracing:
			# kept even after self.operators.clear() below, so a caller
			# can serialize this Rule (and everything under it) once the
			# whole rule tree has finished executing
			self.executedChildren = trace
		self.operators.clear()
	
	def __str__(self):
		return self.operator.__name__
	
	def to_dict(self):
		"""
		Generation record for this Rule and everything that executed underneath
		it for one specific building. Requires context.tracing during execute().
		"""
		parameters = {}
		if hasattr(self, "value"):
			parameters["value"] = encode_value(self.value)
		if self.args:
			parameters["args"] = encode_value(list(self.args))
		if self.kwargs:
			parameters["kwargs"] = encode_value(dict(self.kwargs))

		result = {
			"operator": "Rule",
			"rule": self.operator.__name__,
			"parameters": parameters,
		}
		children = getattr(self, "executedChildren", None)
		if children:
			result["children"] = children
		return result
