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


# Zoning-style lot-dimension table, the way a real subdivision ordinance
# specifies minimum/maximum frontage and depth per zoning district instead
# of a single formula interpolated against one density number. Keyed by
# the same "role" values _stamp_plot_type already assigns (civic roles
# fall back to the district they read closest to -- see ROLE_TO_ZONE).
ZONING_RULES = {
    # tight, deep commercial-frontage lots on the market square/main street
    "commercial": dict(min_frontage=6.0, max_frontage=9.0, min_depth=12.0, max_depth=20.0, gap=0.3),
    # dense inner-ring rowhouse-style plots (kamienice, workshops)
    "residential_dense": dict(min_frontage=6.5, max_frontage=11.0, min_depth=8.0, max_depth=15.0, gap=0.4),
    # looser mid-ring lots (cottages)
    "residential_mid": dict(min_frontage=8.0, max_frontage=13.0, min_depth=7.5, max_depth=14.0, gap=1.0),
    # spacious edge-of-town lots (villas, barns) -- more frontage and gap
    "residential_edge": dict(min_frontage=10.0, max_frontage=16.0, min_depth=7.0, max_depth=13.0, gap=2.0),
}

# Decision tree from a block/plot's *role* (already assigned by
# _assign_plot_types based on function: civic, commercial frontage,
# inner-ring housing, etc.) to the zoning district whose dimensions apply.
# This is what makes lot size follow *use*, the way an actual plat does,
# rather than only distance-from-center.
ROLE_TO_ZONE = {
    "church": "commercial", "ratusz": "commercial", "synagogue": "commercial",
    "workshop": "residential_dense", "kamienica": "residential_dense",
    "cottage": "residential_mid",
    "villa": "residential_edge", "barn": "residential_edge",
}


def zone_for_role(role):
    return ROLE_TO_ZONE.get(role, "residential_dense")


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
    zone=None,
    edge_setbacks=None,
):
    """
    Place rectangular plots along every long edge of a convex block.

    Returns a list of dicts: polygon (4 CCW pts, street edge first),
    width, depth, centroid. Caller assigns role/roof/wall.

    zone: optional key into ZONING_RULES (e.g. "commercial",
        "residential_dense"). When given, lot frontage/depth/gap come from
        that zoning district's rule table instead of being interpolated
        purely from `density` -- e.g. a commercial frontage lot near the
        edge of town still gets tight, deep commercial dimensions, and a
        villa lot near downtown still gets spacious edge-style dimensions,
        which the old density-only formula couldn't express. When zone is
        None (the default), behavior is unchanged from before: dimensions
        are interpolated from density alone.

    edge_setbacks: optional list, one entry per polygon edge (same
        indexing as `polygon`: entry i is the edge from polygon[i] to
        polygon[(i+1) % n]), giving how far in meters to pull that edge's
        row of plots back from the block boundary before laying out
        frontage. This exists because a block's boundary edge is also the
        *road centerline* it borders (see layout.py: roads are the shared
        edges between neighboring Voronoi cells) -- roads are drawn later
        as ribbons with real width (city_builder.py's build_roads), so
        without a setback a plot's street-facing wall would sit on the
        road centerline and the road ribbon would bury the front half of
        every house along it. Pass half the road's width (plus a small
        sidewalk/verge margin) here; see layout.py's
        `_block_edge_setbacks` for the helper that computes this from a
        block's polygon and the layout's road list. Edges that don't
        border a road (e.g. the outer city boundary) should get 0. When
        edge_setbacks is None (the default), behavior is unchanged from
        before: plots are placed flush with the block edge.
    """
    if rng is None:
        rng = randomlib.Random()
    if len(polygon) < 3:
        return []

    center = _centroid(polygon)
    if zone is not None:
        rule = ZONING_RULES.get(zone, ZONING_RULES["residential_dense"])
        frontage_lo, frontage_hi = rule["min_frontage"], rule["max_frontage"]
        depth_lo, depth_hi = rule["min_depth"], rule["max_depth"]
        gap = rule["gap"]
    else:
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

        # Pull this edge's frontage line back off the block boundary (=
        # road centerline) by the road's half-width + verge, so the
        # house wall lands at the road's actual paved edge instead of
        # straddling its centerline. a/b are only translated inward --
        # edge_len and direction are unaffected -- so every offset below
        # (t, frontage, corner_margin) still measures distance along the
        # same street frontage.
        setback = edge_setbacks[i] if edge_setbacks else 0.0
        if setback:
            a = _add(a, _mul(inward, setback))
            b = _add(b, _mul(inward, setback))

        t = corner_margin
        limit = edge_len - corner_margin
        while t + frontage_lo <= limit:
            remaining = limit - t
            frontage = rng.uniform(frontage_lo, frontage_hi)
            if frontage > remaining:
                if remaining >= frontage_lo:
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
