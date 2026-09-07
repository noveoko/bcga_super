from .base import ComplexOperator, context


def openings(wall_height, **kwargs):
    """
    Build a partition wall as piers + lintel from Opening records on the
    current 2-D wall shape (shape.openings). With no openings, this is
    extrude(wall_height).
    """
    return context.factory["Openings"](wall_height, **kwargs)


class Openings(ComplexOperator):
    def __init__(self, wall_height, **kwargs):
        self.wall_height = float(wall_height)
        self.min_pier = float(kwargs.get("min_pier", 0.25))
        super().__init__(0)
