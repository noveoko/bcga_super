from ..runtime.context import context
from .choice import Choice
from .random import Random


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
