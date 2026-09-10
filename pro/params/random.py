from ..runtime.context import context


def random(low, high):
	return Random(low, high)


class Random:
	def __init__(self, low, high):
		self.value = None
		self.low = low
		self.high = high
	
	def getValue(self, rng=None):
		"""Resolve once. `rng` may be a RandomContext or random.Random; default is the ambient session RNG."""
		if self.value is None:
			r = context.random if rng is None else rng
			self.value = r.uniform(self.low, self.high)
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
