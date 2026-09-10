"""
Room partitioner: turn a convex floorplate into rooms + thick internal walls.

No bpy. Used by the partition() operator (and tests) the same way parcels.py
is used by city layout — a pure 2-D split of a polygon, one level down.

Algorithm: optional inset (margin), optional street-to-back corridor, then
recursive longest-axis bisection with a wall strip of `thickness` on each cut
(the same "cut the long way" idea as pro.city.layout._subdivide_block).

2D primitives live in pro.geom (not here) so openings/doors can depend on
geometry without a rooms ↔ openings import cycle.
"""
import math
import random as randomlib

from .geom import (  # noqa: F401 — also re-exported for older `from pro.rooms import _*`
    _AREA_EPS,
    _SPAN_EPS,
    _add,
    _centroid,
    _clip_half,
    _clip_polygon,
    _cross,
    _dot,
    _edge_inward,
    _inset_convex,
    _len,
    _longest_edge_axis,
    _mul,
    _norm,
    _point_in_convex,
    _polygon_area,
    _span_along,
    _sub,
    _valid_poly,
    _width_depth,
)
from .openings import place_openings_from_adjacency


def _record_room(poly, role="room"):
    w, d = _width_depth(poly)
    c = _centroid(poly)
    return {
        "polygon": [[round(x, 6), round(y, 6)] for x, y in poly],
        "area": round(_polygon_area(poly), 6),
        "width": round(w, 6),
        "depth": round(d, 6),
        "centroid": [round(c[0], 6), round(c[1], 6)],
        "role": role,
    }


def _record_wall(poly):
    w, d = _width_depth(poly)
    c = _centroid(poly)
    return {
        "polygon": [[round(x, 6), round(y, 6)] for x, y in poly],
        "length": round(d, 6),
        "thickness": round(w, 6),
        "centroid": [round(c[0], 6), round(c[1], 6)],
        "openings": [],
    }


def _split_with_wall(poly, thickness, min_span, rng):
    """
    One thick cut perpendicular to the longest edge.
    Returns (pos_room, neg_room, wall) or (None, None, None) if it won't fit.
    """
    length, edgeDir, _mid = _longest_edge_axis(poly)
    if length - thickness < 2 * min_span - _SPAN_EPS:
        return None, None, None

    lo, hi = _span_along(poly, edgeDir)
    # wall centered at t; each leftover span along edgeDir must be >= min_span
    t_lo = lo + min_span + thickness / 2.0
    t_hi = hi - min_span - thickness / 2.0
    if t_hi < t_lo - _SPAN_EPS:
        return None, None, None
    frac = rng.uniform(0.42, 0.58)
    t = lo + (hi - lo) * frac
    t = max(t_lo, min(t_hi, t))

    c = _centroid(poly)
    offset = t - _dot(c, edgeDir)
    splitPoint = _add(c, _mul(edgeDir, offset))
    n = edgeDir
    half = thickness / 2.0
    pos = _clip_half(poly, _add(splitPoint, _mul(n, half)), n)
    neg = _clip_half(poly, _add(splitPoint, _mul(n, -half)), _mul(n, -1))
    wall = _clip_half(poly, _add(splitPoint, _mul(n, -half)), n)
    wall = _clip_half(wall, _add(splitPoint, _mul(n, half)), _mul(n, -1))
    if not (_valid_poly(pos) and _valid_poly(neg) and _valid_poly(wall)):
        return None, None, None
    pos_w, pos_d = _width_depth(pos)
    neg_w, neg_d = _width_depth(neg)
    if min(pos_w, pos_d) < min_span - 1e-6 or min(neg_w, neg_d) < min_span - 1e-6:
        return None, None, None
    return pos, neg, wall


def _subdivide(poly, thickness, min_span, max_span, rng, depth, max_depth, rooms, walls):
    length, _edgeDir, _mid = _longest_edge_axis(poly)
    if length <= max_span or depth >= max_depth:
        rooms.append(poly)
        return
    pos, neg, wall = _split_with_wall(poly, thickness, min_span, rng)
    if wall is None:
        rooms.append(poly)
        return
    walls.append(wall)
    _subdivide(pos, thickness, min_span, max_span, rng, depth + 1, max_depth, rooms, walls)
    _subdivide(neg, thickness, min_span, max_span, rng, depth + 1, max_depth, rooms, walls)


def _corridor_cut(poly, corridor, thickness, rng):
    """
    Through-hall from front edge (verts 0→1) to the opposite side.
    Corridor strip is a room; the two long sides are walls.
    Returns (side_polys, corridor_room, side_walls) or None if it doesn't fit.
    """
    if len(poly) < 3 or corridor is None or corridor <= 0:
        return None
    a, b = poly[0], poly[1]
    front_len = _len(_sub(b, a))
    front_dir, _inward = _edge_inward(a, b, poly)
    need = corridor + 2.0 * thickness
    if front_len + 1e-9 < need:
        return None
    lo = thickness
    hi = front_len - corridor - thickness
    t0 = rng.uniform(lo, hi) if hi > lo + 1e-12 else lo

    def at(s):
        return _add(a, _mul(front_dir, s))

    # corridor room: front_dir in [t0, t0+corridor]
    room = _clip_half(poly, at(t0), front_dir)
    room = _clip_half(room, at(t0 + corridor), _mul(front_dir, -1))
    # walls on either long side
    left_wall = _clip_half(poly, at(t0 - thickness), front_dir)
    left_wall = _clip_half(left_wall, at(t0), _mul(front_dir, -1))
    right_wall = _clip_half(poly, at(t0 + corridor), front_dir)
    right_wall = _clip_half(right_wall, at(t0 + corridor + thickness), _mul(front_dir, -1))
    # leftovers beyond the walls
    left = _clip_half(poly, at(t0 - thickness), _mul(front_dir, -1))
    right = _clip_half(poly, at(t0 + corridor + thickness), front_dir)

    if not _valid_poly(room):
        return None
    walls = []
    sides = []
    if _valid_poly(left_wall):
        walls.append(left_wall)
    if _valid_poly(right_wall):
        walls.append(right_wall)
    if _valid_poly(left):
        sides.append(left)
    if _valid_poly(right):
        sides.append(right)
    if len(walls) < 1:
        return None
    return sides, room, walls


def partition_polygon(
    polygon,
    thickness=0.12,
    min_span=2.0,
    max_span=4.5,
    margin=0.0,
    corridor=None,
    rng=None,
    seed=None,
    max_depth=8,
    door_width=None,
    door_height=2.1,
    door_sill=0.0,
    min_pier=0.25,
):
    """
    Partition a convex CCW floorplate into rooms and internal wall strips.

    Returns {"rooms": [...], "walls": [...]} with polygon/area/width/depth
    (rooms) or polygon/length/thickness (walls). Empty input yields empty lists.
    """
    if rng is None:
        rng = randomlib.Random(seed)
    if not _valid_poly(polygon):
        return {"rooms": [], "walls": []}
    if _polygon_area(polygon) < 0:
        polygon = list(reversed(polygon))

    working = _inset_convex(polygon, margin)
    if not _valid_poly(working):
        return {"rooms": [], "walls": []}

    rooms = []
    walls = []
    pieces = [working]
    hall_poly = None
    if corridor:
        cut = _corridor_cut(working, corridor, thickness, rng)
        if cut is not None:
            sides, hall, side_walls = cut
            walls.extend(side_walls)
            rooms.append(hall)
            hall_poly = hall
            pieces = sides

    for piece in pieces:
        _subdivide(piece, thickness, min_span, max_span, rng, 0, max_depth, rooms, walls)

    room_records = []
    for i, p in enumerate(rooms):
        rec = _record_room(p, role="hall" if p is hall_poly else "room")
        rec["id"] = i
        room_records.append(rec)
    wall_records = [_record_wall(p) for p in walls]
    if door_width:
        place_openings_from_adjacency(
            room_records,
            wall_records,
            width=door_width,
            height=door_height,
            sill_height=door_sill,
            min_pier=min_pier,
        )
    return {
        "rooms": room_records,
        "walls": wall_records,
    }
