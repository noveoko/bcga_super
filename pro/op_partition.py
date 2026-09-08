from .base import Operator, ComplexOperator, context, countOperator
from .openings import WallSegment

wall = "wall"
room = "room"


def partition(*parts, **kwargs):
    """
    Partition the current 2-D floorplate into rooms by inserting thick
    internal walls. The current shape is the footprint.

    Selectors (same >> convention as extrude/decompose):
        wall >> InteriorWall()
        room >> RoomFinish()
    or pass them as kwargs: partition(wall=InteriorWall(), room=RoomFinish(), ...)

    Kwargs:
        thickness (float): wall thickness in meters. Default 0.12.
        margin (float): inset before splitting, so walls sit off the exterior.
        min_span (float): stop if a leftover room would be smaller. Default 2.0.
        max_span (float): keep splitting while the longest edge exceeds this.
        corridor (float|None): through-hall width from front edge 0→1.
        seed (int|None): RNG seed for cut jitter.
        max_depth (int): recursion cap. Default 8.
        door_width (float|None): if set, place doors from the room adjacency
            graph (spanning tree from the hall / largest room) instead of
            punching a hole in every wall.
        door_height (float): clear opening height. Default 2.1.
        door_sill (float): sill height. Default 0 (doors on the floor plate).
        min_pier (float): minimum solid wall on each side of a door. Default 0.25.
        lights (bool): if True, hang point lights from a random subset of
            rooms on this floor. Needs `height` (clear storey height).
        height (float|None): clear height of this storey, used with lights.
        light_drop (float): how far below the ceiling slab the lamp hangs.
    """
    return context.factory["Partition"](*parts, **kwargs)


def segment(start, end, thickness=0.12):
    return WallSegment(start, end, thickness)


partition.segment = segment


class Partition(ComplexOperator):
    def __init__(self, *parts, **kwargs):
        self.thickness = float(kwargs.get("thickness", 0.12))
        self.min_span = float(kwargs.get("min_span", 2.0))
        self.max_span = float(kwargs.get("max_span", 4.5))
        self.margin = float(kwargs.get("margin", 0.0))
        corridor = kwargs.get("corridor", None)
        self.corridor = None if corridor is None else float(corridor)
        self.seed = kwargs.get("seed", None)
        self.max_depth = int(kwargs.get("max_depth", 8))
        door_width = kwargs.get("door_width", None)
        self.door_width = None if door_width is None else float(door_width)
        self.door_height = float(kwargs.get("door_height", 2.1))
        self.door_sill = float(kwargs.get("door_sill", 0.0))
        self.min_pier = float(kwargs.get("min_pier", 0.25))
        self.lights = bool(kwargs.get("lights", False))
        height = kwargs.get("height", None)
        self.height = None if height is None else float(height)
        self.light_drop = float(kwargs.get("light_drop", 0.22))
        self.wall = None
        self.room = None

        numOperators = 0
        for arg in parts:
            if isinstance(arg, Operator):
                if hasattr(arg, "value") and isinstance(arg.value, str):
                    setattr(self, arg.value, arg)
                if countOperator(arg):
                    numOperators += 1
        for key in ("wall", "room"):
            if kwargs.get(key) is not None:
                setattr(self, key, kwargs[key])
                if countOperator(kwargs[key]):
                    numOperators += 1
        super().__init__(numOperators)
