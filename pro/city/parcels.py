"""
Street-edge parceler: turn a convex city block into human-scale rectangular
building plots along its edges, leaving a courtyard in the middle.

No bpy. Used by layout.py to produce layout["plots"].
"""
import math
import random as randomlib


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


def _point_in_convex(p, poly, eps=0.05):
    """CCW convex polygon: p is inside if it is to the left of every edge."""
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if _cross(_sub(b, a), _sub(p, a)) < -eps:
            return False
    return True


def _aabb(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return (min(xs), min(ys), max(xs), max(ys))


def _aabb_overlap(a, b, gap=0.15):
    # Treat boxes as overlapping if they intersect or come within `gap`.
    return not (
        a[2] + gap <= b[0] or b[2] + gap <= a[0]
        or a[3] + gap <= b[1] or b[3] + gap <= a[1]
    )


def _rects_overlap(r1, r2, gap=0.15):
    return _aabb_overlap(_aabb(r1), _aabb(r2), gap=gap)


def _rectangle_on_edge(a, b, t0, frontage, depth, inward):
    """
    CCW rectangle: street edge is p0→p1, then into the block p1→p2→p3.
    t0 is distance along A→B in meters.
    """
    edge = _sub(b, a)
    direction = _norm(edge)
    p0 = _add(a, _mul(direction, t0))
    p1 = _add(a, _mul(direction, t0 + frontage))
    p2 = _add(p1, _mul(inward, depth))
    p3 = _add(p0, _mul(inward, depth))
    return [p0, p1, p2, p3]


def parcel_block(
    polygon,
    density=0.5,
    rng=None,
    min_frontage=6.5,
    max_frontage=14.0,
    min_depth=7.0,
    max_depth=16.0,
    min_edge=8.0,
    corner_margin=0.6,
):
    """
    Place rectangular plots along every long edge of a convex block.

    Returns a list of dicts: polygon (4 CCW pts, street edge first),
    width, depth, centroid. Caller assigns role/roof/wall.
    """
    if rng is None:
        rng = randomlib.Random()
    if len(polygon) < 3:
        return []

    center = _centroid(polygon)
    # tighter, shallower lots downtown; looser cottages on the edge
    frontage_lo = min_frontage + (1.0 - density) * 1.5
    frontage_hi = max_frontage - density * 2.0
    if frontage_hi < frontage_lo + 0.5:
        frontage_hi = frontage_lo + 0.5
    depth_lo = min_depth + density * 1.5
    depth_hi = max_depth - (1.0 - density) * 3.0
    if depth_hi < depth_lo + 0.5:
        depth_hi = depth_lo + 0.5
    gap = 0.25 + (1.0 - density) * 1.8

    plots = []
    n = len(polygon)
    for i in range(n):
        a, b = polygon[i], polygon[(i + 1) % n]
        edge = _sub(b, a)
        edge_len = _len(edge)
        if edge_len < min_edge:
            continue
        direction = _norm(edge)
        inward = (-direction[1], direction[0])  # left of CCW edge = inside
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if _dot(inward, _sub(center, mid)) < 0:
            inward = (-inward[0], -inward[1])

        t = corner_margin
        limit = edge_len - corner_margin
        while t + min_frontage <= limit:
            remaining = limit - t
            frontage = rng.uniform(frontage_lo, frontage_hi)
            if frontage > remaining:
                if remaining >= min_frontage:
                    frontage = remaining
                else:
                    break
            depth = rng.uniform(depth_lo, depth_hi)
            rect = _rectangle_on_edge(a, b, t, frontage, depth, inward)
            if all(_point_in_convex(p, polygon) for p in rect) and not any(
                _rects_overlap(rect, existing["polygon"]) for existing in plots
            ):
                cx = sum(p[0] for p in rect) / 4.0
                cy = sum(p[1] for p in rect) / 4.0
                plots.append({
                    "polygon": [[round(x, 4), round(y, 4)] for x, y in rect],
                    "width": round(frontage, 2),
                    "depth": round(depth, 2),
                    "centroid": [round(cx, 4), round(cy, 4)],
                })
                t += frontage + gap
            else:
                t += 1.0
    return plots
