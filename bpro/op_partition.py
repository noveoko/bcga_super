import pro
from pro import context
from pro.rooms import partition_polygon

from .shape import Shape2d, createRectangle, createShape2d


def _shape_xy(shape):
    loop = shape.firstLoop
    start = loop
    pts = []
    zs = []
    while True:
        co = loop.vert.co
        pts.append((co[0], co[1]))
        zs.append(co[2])
        loop = loop.link_loop_next
        if loop == start:
            break
    z = sum(zs) / len(zs)
    return pts, z


def _shape_from_poly(poly, z):
    verts = [context.vertexRegistry.getVertex((p[0], p[1], z)) for p in poly]
    if len(verts) == 4:
        return createRectangle(verts)
    return createShape2d(verts)


class Partition(pro.op_partition.Partition):
    def execute(self):
        shape = context.getState().shape
        if not isinstance(shape, Shape2d):
            return
        poly, z = _shape_xy(shape)
        result = partition_polygon(
            poly,
            thickness=self.thickness,
            min_span=self.min_span,
            max_span=self.max_span,
            margin=self.margin,
            corridor=self.corridor,
            seed=self.seed,
            max_depth=self.max_depth,
            door_width=self.door_width,
            door_height=self.door_height,
            door_sill=self.door_sill,
            min_pier=self.min_pier,
        )
        context.facesForRemoval.append(shape.face)
        jobs = [(item, self.wall, True) for item in result["walls"]]
        jobs += [(item, self.room, False) for item in result["rooms"]]
        for item, rule, is_wall in jobs:
            new_shape = _shape_from_poly(item["polygon"], z)
            if is_wall:
                new_shape.openings = item.get("openings") or []
            if rule:
                context.pushState(shape=new_shape)
                rule.execute()
                context.popState()
