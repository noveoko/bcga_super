from .modifier import Modifier
from ..params.parameter import Param
from ..rule_context import ambient_operator_parent
from ..serialization.trace import (
	_SERIALIZE_SKIP_ATTRS,
	_STRUCTURAL_ATTRS,
	encode_param,
	encode_value,
)


def countOperator(o):
	"""
	A helper function that checks if its argument must be counted as BCGA Operator
	in a constructor of the other operators. Every operator can be counted once.
	The function also sets count attribute to False in the positive case when it returns True
	
	Returns:
	    bool: True if the operator must be counted, False otherwise
	"""
	if isinstance(o, Operator) and o.count:
		result = True
		o.count = False
	else:
		result = False
	return result


class Operator:
	def __init__(self):
		# Every operator can be counted once time in a constructor of the other operators
		# self.count is set to False in the countOperator helper function
		self.count = True
		# Register under the current rule parent when inside a rule body.
		# Outside a rule body (unit tests constructing ops directly) there is
		# no parent — skip instead of requiring a dummy context.operator.
		parent = ambient_operator_parent()
		if parent is not None:
			parent.addChildOperator(self)
	
	def bind_param(self, name, authored, resolve=float):
		"""
		Remember an authored parameter source and store its resolved value on self.<name>.

		Generation records use the authored object (Random/Choice/Param/…) plus the
		resolved runtime value. Pass resolve=None to keep authored as-is on the attribute.
		"""
		if not hasattr(self, "_param_authored") or self._param_authored is None:
			self._param_authored = {}
		self._param_authored[name] = authored
		if resolve is None:
			resolved = authored
		else:
			resolved = resolve(authored)
		setattr(self, name, resolved)
		return resolved

	def __rrshift__(self, value):
		# The operator to be returned.
		# We create a wrapper RrshiftOperator if >> already was applied to the operator instance
		wrapper = False
		if hasattr(self, "value"):
			operator = RrshiftOperator(self)
			wrapper = True
		else:
			operator = self
		if isinstance(value, Modifier):
			setattr(operator, value.modifier, True)
			operator.value = value.value
			if wrapper:
				wrapper.modifier = value.modifier
		elif isinstance(value, Param):
			operator.value = value.value
		else:
			operator.value = value
		return operator
	
	def execute(self, ctx=None):
		"""Run this operator. Prefer passing an explicit RuleContext (Phase 3)."""
		pass
	
	def execute_join(self, band, ctx=None):
		""" This method should be called for each band of rectangles after join(..) finished its procession"""
		pass
	
	def __call__(self):
		# NOTE: the line context.operator.addChildOperator(self) was required before
		# to avoid error.
		# Now that line causes eroor, so it was commented out
		#context.operator.addChildOperator(self)
		return self
	
	def __str__(self):
		return self.__class__.__name__
	
	def to_dict(self):
		"""
		Generation record for this operator: authored vs resolved parameters,
		plus nested parts/children. Populated meaningfully when context.tracing
		was True during execution -- see Rule.executeChildOperators().
		"""
		result = {"operator": self.__class__.__name__, "parameters": {}}
		authored = getattr(self, "_param_authored", None) or {}
		class_skip = getattr(type(self), "_TRACE_SKIP", ()) or ()

		for name, auth in authored.items():
			result["parameters"][name] = encode_param(auth, getattr(self, name, None))

		# Remaining public attrs → literal/structured parameter cells
		skip = set(_SERIALIZE_SKIP_ATTRS) | set(authored) | set(_STRUCTURAL_ATTRS) | set(class_skip)
		for k, v in vars(self).items():
			if k in skip or k.startswith("_"):
				continue
			if k in result["parameters"]:
				continue
			result["parameters"][k] = encode_value(v)

		parts = getattr(self, "parts", None)
		if parts:
			result["parts"] = [encode_value(p) for p in parts]

		insets = getattr(self, "insets", None)
		if insets:
			result["insets"] = [encode_value(p) for p in insets]

		cases = getattr(self, "cases", None)
		if cases is not None:
			result["cases"] = encode_value(cases)

		default = getattr(self, "default", None)
		if default is not None:
			result["default"] = encode_value(default)

		children = getattr(self, "executedChildren", None)
		if children:
			result["children"] = children
		return result


class RrshiftOperator:
	"""A wrapper class to support multiple usage of operators with >>"""
	def __init__(self, operator):
		# operator has been alread counted
		self.count = False
		self.modifier = None
		self.operator = operator
	
	def execute(self, ctx=None):
		operator = self.operator
		# remember original value for self.operator
		value = self.value
		operator.value = self.value
		self.operator.execute(ctx)
		if self.modifier:
			delattr(operator, self.modifier)
		# restore the original value
		operator.value = value
		if self.modifier:
			setattr(operator, self.modifier, True)


class ComplexOperator(Operator):
	def __init__(self, numParts):
		# remove numParts operators from the current parent when inside a rule
		parent = ambient_operator_parent()
		if parent is not None:
			parent.removeChildOperators(numParts)
		super().__init__()


class OperatorDef:
	def __init__(self, *operators):
		self.parts = list(operators)
		self.repeat = False
	
	def __repr__(self):
		result = ""
		if self.repeat: result += "(repeat)"
		result += "["
		firstPart = True
		for part in self.parts:
			if firstPart:
				firstPart = False
			else:
				result += " | "
			result += str(part)
		result += "]"
		return result
