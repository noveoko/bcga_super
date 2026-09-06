import random as randomlib
import json

def flt(value=1):
	return Modifier(flt=value)

def rel(value):
	return Modifier(rel=value)


class Modifier:
	"""
	A wrapper for flt(...) and rel(...) modifiers
	"""
	def __init__(self, **kwargs):
		for k in kwargs:
			# there is only one kwarg!
			self.modifier = k
			setattr(self, k, True)
			self.value = kwargs[k]
	
	def execute(self):
		pass


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


# instance attributes that are internal bookkeeping only, and shouldn't
# appear in a serialized (to_dict/JSON) view of an operator
_SERIALIZE_SKIP_ATTRS = {"count"}


def _serialize_value(v):
	"""
	Converts a single attribute value from an Operator/Rule instance into
	something JSON-serializable. Used by Operator.to_dict()/Rule.to_dict().
	"""
	if isinstance(v, Operator):
		return v.to_dict()
	if isinstance(v, Modifier):
		return {"modifier": v.modifier, "value": _serialize_value(v.value)}
	if isinstance(v, Random):
		# low/high are the authored range; resolved is the value actually
		# used for this specific generated building
		return {"random": [v.low, v.high], "resolved": v.getValue()}
	if isinstance(v, Param):
		return v.getValue()
	if isinstance(v, (list, tuple)):
		return [_serialize_value(x) for x in v]
	if isinstance(v, dict):
		return {str(k2): _serialize_value(x) for k2, x in v.items()}
	if isinstance(v, (int, float, str, bool)) or v is None:
		return v
	# Fallback for anything we don't have a specific rule for (e.g. internal
	# helper objects like SplitDef/RawValue, or a plain Python function
	# reference). This keeps to_dict() from ever raising on unknown types;
	# it just degrades to a readable string instead of failing the export.
	return str(v)


class Operator:
	def __init__(self):
		# Every operator can be counted once time in a constructor of the other operators
		# self.count is set to False in the countOperator helper function
		self.count = True
		context.operator.addChildOperator(self)
	
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
	
	def execute(self):
		pass
	
	def execute_join(self, band):
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
		Returns a JSON-serializable dict describing this operator instance
		as it was actually resolved for one specific generated building
		(all randomness already settled, all param values resolved).
		Only populated meaningfully when context.tracing was True during
		execution -- see Rule.executeChildOperators().
		"""
		result = {"type": self.__class__.__name__}
		for k, v in vars(self).items():
			if k in _SERIALIZE_SKIP_ATTRS:
				continue
			result[k] = _serialize_value(v)
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
	
	def execute(self):
		operator = self.operator
		# remember original value for self.operator
		value = self.value
		operator.value = self.value
		self.operator.execute()
		if self.modifier:
			delattr(operator, self.modifier)
		# restore the original value
		operator.value = value
		if self.modifier:
			setattr(operator, self.modifier, True)


class ComplexOperator(Operator):
	def __init__(self, numParts):
		# remove numParts operators from
		context.operator.removeChildOperators(numParts) 
		super().__init__()


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
	
	def execute(self):
		# setting the current operator to self
		context.operator = self
		self.operator(*self.args, **self.kwargs)
		self.executeChildOperators()

	def addChildOperator(self, operator):
		"""Adds child operator"""
		self.operators.append(operator)
	
	def removeChildOperators(self, numOperators):
		while numOperators:
			self.operators.pop()
			numOperators -= 1
	
	def executeChildOperators(self):
		# execute operators inside the body of the current operator
		tracing = context.tracing
		trace = [] if tracing else None
		for o in self.operators:
			o.execute()
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
		Returns a JSON-serializable dict describing this Rule and everything
		that executed underneath it, as actually resolved for one specific
		generated building. Requires context.tracing to have been True
		during execute(), otherwise "children" will be empty.
		"""
		result = {"type": "Rule", "rule": self.operator.__name__}
		if hasattr(self, "value"):
			result["value"] = _serialize_value(self.value)
		if self.args:
			result["args"] = [_serialize_value(a) for a in self.args]
		if self.kwargs:
			result["kwargs"] = {k: _serialize_value(v) for k, v in self.kwargs.items()}
		children = getattr(self, "executedChildren", None)
		if children:
			result["children"] = children
		return result


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


class State:
	def __init__(self, **kwargs):
		for k in kwargs:
			setattr(self, k, kwargs[k])
		self.valid = True


class Context:
	def __init__(self):
		# when True, Rule.executeChildOperators() records a resolved,
		# JSON-serializable trace of everything that executes (see
		# Operator.to_dict()/Rule.to_dict()). False by default so
		# normal generation has zero extra overhead.
		self.tracing = False
		# set by city_builder.py before each block is generated
		self.cityBlock = None
		self.reset()
		
	def reset(self):
		# the factory stores references to the basic classes
		self.factory = {}
	
	def __call__(self):
		self.reset()
	
	def addAttribute(self, attr, value):
		setattr(self, attr, value)
		self.attrs.append(attr)
	
	def removeAttributes(self):
		for attr in self.attrs:
			delattr(self, attr)
		self.attrs = []
	
	def getState(self):
		return self.stack[-1]
	
	def pushState(self, **kwargs):
		# create a new execution state entry
		state = State(**kwargs)
		self.stack.append(state)
		return state
	
	def popState(self):
		self.stack.pop()
	
	def registerParam(self, param):
		self.params.append(param)
		
	def init(self):
		# implementation specific attributes
		self.attrs = []
		# stack to track branching
		self.stack = []
		self.deferreds = []
		# the list of params
		self.params = []
	
	def prepare(self):
		"""The method does all necessary preparations for a rule evaluation."""
		# set random values for the random params from self.params
		for param in self.params:
			if param.random:
				param.assignValue()
	
	def addDeferred(self, shape, deferredOperator):
		self.deferreds.append((shape, deferredOperator))
	
	def executeDeferred(self):
		self.joinManager = self.joinManager()
		for entry in self.deferreds:
			# entry[1] is operator
			# entry[0] is shape
			entry[1].resolve(entry)
		self.joinManager.finalize()


def shape():
	"""Returns the current (top) shape from the stack"""
	context.operator.executeChildOperators()
	return context.getState().shape


#
# Parameters stuff
#

def param(value, group=None, unit=None, min=None, max=None):
	# Choice wraps a value to be resolved once per generated building;
	# peek at a representative option to decide float vs color dispatch
	probe = value.options[0] if isinstance(value, Choice) else value
	if isinstance(probe, str) and probe[0]=="#":
		result = ParamColor(value)
	else:
		result = ParamFloat(value, min=min, max=max)
	result.group = group
	result.unit = unit
	return result

class Choice:
	"""
	A discrete counterpart to random(low, high): picks ONE value from a
	fixed set of options, resolved once per generated building (same
	one-shot-resolution semantics as Random -- see getValue()).

	Usage:
		color(choice("#a83232", "#3255a8", "#32a852"))
		STYLE = param(choice(1, 2, 3), group="Facade")
		choice("brick", "stone", weights=[0.7, 0.3])
	"""
	def __init__(self, *options, weights=None):
		if not options:
			raise ValueError("choice() needs at least one option")
		if weights is not None and len(weights) != len(options):
			raise ValueError("choice() got %d weights for %d options" % (len(weights), len(options)))
		self.options = options
		self.weights = weights
		self.value = None

	def getValue(self):
		if self.value is None:
			if self.weights:
				self.value = randomlib.choices(self.options, weights=self.weights, k=1)[0]
			else:
				self.value = randomlib.choice(self.options)
		return self.value

	def __str__(self):
		return str(self.getValue())

	def __float__(self):
		return float(self.getValue())


def choice(*options, weights=None):
	return Choice(*options, weights=weights)


def random(low, high):
	return Random(low, high)


class Param:
	def setValue(self, value):
		self.value = value
		
	def __str__(self):
		return str(self.value)
	
	def getValue(self):
		return self.value

	def execute(self):
		pass


class ParamFloat(Param):
	def __init__(self, value, min=None, max=None):
		self.min = min
		self.max = max
		if isinstance(value, (Random, Choice)):
			self.value = None
			self.random = value
		else:
			self.value = self._clamp(value)
			self.random = None
		context.registerParam(self)
	
	def _clamp(self, value):
		"""Clamps value into [self.min, self.max], whichever bounds were given via param(value, min=..., max=...)."""
		if self.min is not None and value < self.min:
			value = self.min
		if self.max is not None and value > self.max:
			value = self.max
		return value
	
	def setValue(self, value):
		self.value = self._clamp(value)
	
	def assignValue(self):
		"""Assigns a value for the parameter. Relevant only for random parameters"""
		if self.random:
			self.value = self._clamp(self.random.getValue())
	
	def __float__(self):
		return float(self.value)
	
	def __add__(self, other):
		return self.value + other
	
	def __radd__(self, other):
		return other + self.value
	
	def __sub__(self, other):
		return self.value - other
	
	def __rsub__(self, other):
		return other - self.value
	
	def __mul__(self, other):
		return self.value * other
	
	def __rmul__(self, other):
		return other * self.value
	
	def __truediv__(self, other):
		return self.value/other
	
	def __rtruediv__(self, other):
		return other/self.value
	
	def __neg__(self):
		return -self.value
	
	def __abs__(self):
		return abs(self.value)


class ParamColor(Param):
	def __init__(self, value):
		if isinstance(value, Choice):
			self.value = None
			self.choice = value
		else:
			self.value = value
			self.choice = None
	
	def getValue(self):
		self.assignValue()
		# convert from the hex string to a tuple
		return tuple( map(lambda c: c/255, bytes.fromhex(self.value[-6:])) )
	
	def setValue(self, value):
		# convert from the tuple to a hex string
		self.value = "#%02x%02x%02x" % tuple( map(lambda c: round(c*255), value) )
	
	def assignValue(self):
		"""Assigns a value for the parameter. Relevant only for choice-based colors"""
		if self.choice and self.value is None:
			self.value = self.choice.getValue()
	
	def __str__(self):
		self.assignValue()
		return self.value


class Random:
	def __init__(self, low, high):
		self.value = None
		self.low = low
		self.high = high
	
	def getValue(self):
		if self.value is None:
			self.value = randomlib.uniform(self.low, self.high)
		return self.value
	
	def __str__(self):
		return str(self.getValue())

	def __float__(self):
		return float(self.getValue())
	
	def __add__(self, other):
		return self.getValue() + other
	
	def __radd__(self, other):
		return other + self.getValue()
	
	def __sub__(self, other):
		return self.getValue() - other
	
	def __rsub__(self, other):
		return other - self.getValue()
	
	def __mul__(self, other):
		return self.getValue() * other
	
	def __rmul__(self, other):
		return other * self.getValue()
	
	def __truediv__(self, other):
		return self.getValue()/other
	
	def __rtruediv__(self, other):
		return other/self.getValue()
	
	def __neg__(self):
		return -self.getValue()
	
	def __abs__(self):
		return abs(self.getValue())


def to_json(rule, **kwargs):
	"""
	Convenience wrapper: serializes a Rule/Operator (or its already-computed
	to_dict() result) to a JSON string. kwargs are passed through to
	json.dumps (e.g. indent=2).
	"""
	data = rule.to_dict() if hasattr(rule, "to_dict") else rule
	return json.dumps(data, **kwargs)


context = Context()