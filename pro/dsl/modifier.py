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
