from .rule_context import resolve_rule_context
from .base import Operator, context


def material(_material):
    return resolve_rule_context().factory["Material"](_material)


class Material(Operator):
    def __init__(self, _material):
        self.material = _material
        super().__init__()
