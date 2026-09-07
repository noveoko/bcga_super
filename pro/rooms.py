"""
Room partitioner: turn a convex floorplate into rooms + thick internal walls.

No bpy. Used by the partition() operator (and tests) the same way parcels.py
is used by city layout — a pure 2-D split of a polygon, one level down.

Algorithm: optional inset (margin), optional street-to-back corridor, then
recursive longest-axis bisection with a wall strip of `thickness` on each cut
(the same "cut the long way" idea as pro.city.layout._subdivide_block).
"""
import math
import random as randomlib


_AREA_EPS = 1e-6
_SPAN_EPS = 1e-9


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _mul(a, s):
    return (a[0] * s, a[1] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _len(a):
    return math.hypot(a[0], a[1])


def _norm(a):
    L = _len(a)
    if L < 1e-12:
        return (0.0, 0.0)
    return (a[0] / L, a[1] / L)


def _centroid(poly):
    return (
        sum(p[0] for p in poly) / len(poly),
        sum(p[1] for p in poly) / len(poly),
    )


def _polygon_area(poly):
    n = len(poly)
    if n < 3:
        return 0.0
    acc = 0.0
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        acc += a[0] * b[1] - b[0] * a[1]
    return acc * 0.5


def _point_in_convex(p, poly, eps=1e-7):
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if _cross(_sub(b, a), _sub(p, a)) < -eps:
            return False
    return True


def _clip_polygon(subject, clipPoly):
    """Sutherland-Hodgman. clipPoly must be convex and CCW."""
    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0

    def intersect(p1, p2, a, b):
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = a
        x4, y4 = b
        d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(d) < 1e-12:
            return p2
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))

    output = list(subject)
    n = len(clipPoly)
    for i in range(n):
        a, b = clipPoly[i], clipPoly[(i + 1) % n]
        inputList, output = output, []
        if not inputList:
            break
        for j in range(len(inputList)):
            cur, prev = inputList[j], inputList[j - 1]
            curIn, prevIn = inside(cur, a, b), inside(prev, a, b)
            if curIn:
                if not prevIn:
                    output.append(intersect(prev, cur, a, b))
                output.append(cur)
            elif prevIn:
                output.append(intersect(prev, cur, a, b))
    return _dedupe_ring(output)


def _dedupe_ring(poly, tol=1e-9):
    if not poly:
        return []
    out = [poly[0]]
    for p in poly[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > tol:
            out.append(p)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= tol:
        out.pop()
    return out


def _halfplane_quad(point, normal, size=1e5):
    """
    Large convex CCW quad for {p : dot(p - point, normal) >= 0}.
    `perp` is normal rotated -90 deg so (perp, normal) is right-handed.
    """
    perp = (normal[1], -normal[0])
    a = (point[0] - perp[0] * size, point[1] - perp[1] * size)
    b = (point[0] + perp[0] * size, point[1] + perp[1] * size)
    c = (b[0] + normal[0] * size, b[1] + normal[1] * size)
    d = (a[0] + normal[0] * size, a[1] + normal[1] * size)
    return [a, b, c, d]


def _clip_half(poly, point, normal):
    return _clip_polygon(poly, _halfplane_quad(point, normal))


def _valid_poly(poly):
    return poly is not None and len(poly) >= 3 and _polygon_area(poly) > _AREA_EPS


def _edge_inward(a, b, poly):
    direction = _norm(_sub(b, a))
    inward = (-direction[1], direction[0])  # left of CCW edge
    mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    c = _centroid(poly)
    if _dot(inward, _sub(c, mid)) < 0:
        inward = (-inward[0], -inward[1])
    return direction, inward


def _inset_convex(poly, margin):
    if margin <= 0:
        return list(poly)
    result = list(poly)
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        _direction, inward = _edge_inward(a, b, poly)
        offset_pt = _add(a, _mul(inward, margin))
        result = _clip_half(result, offset_pt, inward)
        if not _valid_poly(result):
            return []
    return result


def _longest_edge_axis(poly):
    n = len(poly)
    bestLen, bestDir, bestMid = -1.0, (1.0, 0.0), (0.0, 0.0)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length > bestLen:
            bestLen = length
            bestDir = (dx / length, dy / length) if length > 1e-9 else (1.0, 0.0)
            bestMid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    return bestLen, bestDir, bestMid


def _span_along(poly, axis):
    dots = [_dot(p, axis) for p in poly]
    return min(dots), max(dots)


def _width_depth(poly):
    """width = shorter span, depth = longer span, in the longest-edge frame."""
    _length, edgeDir, _mid = _longest_edge_axis(poly)
    perp = (-edgeDir[1], edgeDir[0])
    long_span = _span_along(poly, edgeDir)
    short_span = _span_along(poly, perp)
    long = long_span[1] - long_span[0]
    short = short_span[1] - short_span[0]
    return short, long


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
        from .openings import place_openings_from_adjacency
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
