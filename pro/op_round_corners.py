from .rule_context import resolve_rule_context
from .base import ComplexOperator, context


def round_corners(radius=0.4, segments=3, **kwargs):
    return resolve_rule_context().factory["RoundCorners"](radius, segments=segments, **kwargs)


class RoundCorners(ComplexOperator):
    def __init__(self, radius=0.4, segments=3, **kwargs):
        self.bind_param("radius", radius, resolve=float)
        self.bind_param("segments", segments, resolve=int)
        super().__init__(0)
