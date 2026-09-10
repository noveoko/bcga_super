from ..runtime.context import context


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
		if weights is not None:
			if any(w < 0 for w in weights):
				raise ValueError("choice() weights must be non-negative")
			if not any(w > 0 for w in weights):
				raise ValueError("choice() needs at least one positive weight")
		self.options = options
		self.weights = weights
		self.value = None

	def getValue(self, rng=None):
		"""Resolve once. `rng` may be a RandomContext or random.Random; default is the ambient session RNG."""
		if self.value is None:
			r = context.random if rng is None else rng
			if self.weights:
				self.value = r.choices(self.options, weights=self.weights, k=1)[0]
			else:
				self.value = r.choice(self.options)
		return self.value

	def __str__(self):
		return str(self.getValue())

	def __float__(self):
		return float(self.getValue())


def choice(*options, weights=None):
	return Choice(*options, weights=weights)
