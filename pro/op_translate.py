from .rule_context import resolve_rule_context
from .base import Operator, context

def translate(dx, dy, dz):
    return resolve_rule_context().factory["Translate"]((dx, dy, dz))


class Translate(Operator):
    def __init__(self, vec):
        # Remember authored components (may include Random/Param) for traces
        self.bind_param("vec", vec, resolve=None)
        super().__init__()