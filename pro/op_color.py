from .rule_context import resolve_rule_context
from .base import Operator, context

def color(_color):
	return resolve_rule_context().factory["Color"](_color)

class Color(Operator):
	def __init__(self, _color):
		authored = _color
		resolved = _color
		if not isinstance(resolved, (str, tuple, list)):
			# Choice/ParamColor/etc. — resolve to a hex string for execution
			resolved = str(resolved)
		if isinstance(resolved, str):
			self.colorHex = resolved
			# we've got a hex string, convert to the tuple
			resolved = tuple( map(lambda c: c/255, bytes.fromhex(resolved[-6:])) )
		else:
			self.colorHex = None
		self.bind_param("color", authored, resolve=lambda _a: resolved)
		super().__init__()