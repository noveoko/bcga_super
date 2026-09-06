from .base import ComplexOperator, context


def round_corners(radius=0.4, segments=3, **kwargs):
    return context.factory["RoundCorners"](radius, segments=segments, **kwargs)


class RoundCorners(ComplexOperator):
    def __init__(self, radius=0.4, segments=3, **kwargs):
        self.radius = float(radius)
        self.segments = int(segments)
        super().__init__(0)
