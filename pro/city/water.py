"""
Water features for the organic city layout: rivers, streams, creeks
(linear, flow along a path with a width), and watersheds, lakes, ponds
(areal, a closed polygon).

This module is pure Python (only needs `math` + the `random.Random`
instance the caller already has for reproducibility) so, like layout.py,
it never depends on Blender and can run as an ordinary script.

Two responsibilities:

1. Generation -- procedurally place water features inside the city disk
   (optionally letting a terrain.ElevationModel nudge rivers toward lower
   ground), for callers that don't already have real hydrology data.
2. Road/water intersection -- given the already-computed "roads" list
   (see layout.py's generate_city_layout) and a list of water features,
   find every place a road crosses water and split that road segment into
   (normal, bridge, normal) pieces, tagging the middle piece so
   city_builder.py can render an actual bridge there instead of a road
   ribbon sitting on/under the water.

Water feature schema (JSON-serializable dicts):

    Linear (river / stream / creek):
        {"id": int, "type": "river"|"stream"|"creek", "name": str,
         "path": [[x, y], ...],  # centerline, >= 2 points
         "width": float,          # meters, bank to bank
         "requires_bridge": True}

    Areal (lake / pond / watershed):
        {"id": int, "type": "lake"|"pond"|"watershed", "name": str,
         "polygon": [[x, y], ...],  # closed ring, CCW or CW, not repeated
         "requires_bridge": bool}   # True for lake/pond; watershed
                                    # (a catchment boundary, not open
                                    # water) defaults to False -- crossing
                                    # it doesn't need a bridge, but callers
                                    # can flip this per-feature if their
                                    # watershed *is* wet (e.g. a marsh).
"""
import math


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_river(rng, radius, terrain=None, width=6.0, num_points=20,
                    meander=0.35, feature_type="river", id_=0, name=None):
    """
    A meandering polyline that crosses the whole city disk, entering and
    exiting through the boundary (so it's guaranteed to interact with the
    road network -- a river that stays in a corner would never test
    bridging). Built as a straight chord between two boundary points,
    then displaced sideways by a tapered random-walk offset (zero at both
    endpoints, so it still exits cleanly through the boundary circle).

    If `terrain` is given, at each interior point the path takes a small
    extra step toward whichever side (left/right of travel) is lower
    elevation -- a cheap stand-in for "water flows downhill" without
    needing a full flow-accumulation model.
    """
    a1 = rng.random() * 2 * math.pi
    # roughly the opposite side of the circle, with some spread so rivers
    # don't all look like diameters
    a2 = a1 + math.pi + (rng.random() - 0.5) * (math.pi * 0.6)
    start = (radius * math.cos(a1), radius * math.sin(a1))
    end = (radius * math.cos(a2), radius * math.sin(a2))

    dx, dy = end[0] - start[0], end[1] - start[1]
    span = math.hypot(dx, dy) or 1.0
    perp = (-dy / span, dx / span)

    # tapered random walk for the lateral offset: cumulative sum of small
    # random steps (smoother than independent-per-point noise), scaled to
    # a fraction of the chord length and tapered to 0 at both ends with a
    # sine window so the path still meets the boundary exactly.
    steps = [rng.random() - 0.5 for _ in range(num_points)]
    walk = []
    total = 0.0
    for s in steps:
        total += s
        walk.append(total)
    peak = max(abs(w) for w in walk) or 1.0

    path = []
    for i in range(num_points):
        t = i / (num_points - 1)
        bx = start[0] + dx * t
        by = start[1] + dy * t
        taper = math.sin(math.pi * t)  # 0 at t=0 and t=1
        amp = span * meander * (walk[i] / peak) * taper
        x, y = bx + perp[0] * amp, by + perp[1] * amp
        if terrain is not None and 0.0 < t < 1.0:
            e_plus = terrain.elevation(x + perp[0] * 2.0, y + perp[1] * 2.0)
            e_minus = terrain.elevation(x - perp[0] * 2.0, y - perp[1] * 2.0)
            nudge = 1.5 if e_plus < e_minus else -1.5
            x, y = x + perp[0] * nudge, y + perp[1] * nudge
        path.append([round(x, 4), round(y, 4)])

    return {
        "id": id_,
        "type": feature_type,
        "name": name or "%s_%d" % (feature_type.capitalize(), id_),
        "path": path,
        "width": width,
        "requires_bridge": True,
    }


def generate_lake(rng, radius, terrain=None, center=None, mean_radius=25.0,
                   irregularity=0.4, num_verts=14, feature_type="lake",
                   id_=0, name=None, requires_bridge=True):
    """
    An irregular closed blob polygon: `num_verts` points at even angular
    spacing around `center`, each pushed in/out from `mean_radius` by up
    to `irregularity` (0 = perfect circle, close to 1 = very jagged).
    If `center` isn't given, one is picked at random inside the city disk
    (kept away from the very edge so the whole shape fits).
    """
    if center is None:
        cr = radius * (0.1 + 0.6 * rng.random())
        ca = rng.random() * 2 * math.pi
        center = (cr * math.cos(ca), cr * math.sin(ca))

    poly = []
    for i in range(num_verts):
        theta = 2 * math.pi * i / num_verts
        r = mean_radius * (1.0 + irregularity * (rng.random() * 2.0 - 1.0))
        x = center[0] + r * math.cos(theta)
        y = center[1] + r * math.sin(theta)
        poly.append([round(x, 4), round(y, 4)])

    return {
        "id": id_,
        "type": feature_type,
        "name": name or "%s_%d" % (feature_type.capitalize(), id_),
        "polygon": poly,
        "requires_bridge": requires_bridge,
    }


def generate_water_bodies(rng, radius, terrain=None,
                           num_rivers=0, num_streams=0, num_creeks=0,
                           num_lakes=0, num_ponds=0, num_watersheds=0,
                           river_width=6.0, stream_width=2.5, creek_width=1.2):
    """
    Convenience bundle: generate however many of each water-feature type
    are requested, with sane per-type default widths/sizes and sequential
    ids. Returns a flat list mixing linear and areal features.
    """
    features = []
    fid = 0
    for ftype, count, width in (
        ("river", num_rivers, river_width),
        ("stream", num_streams, stream_width),
        ("creek", num_creeks, creek_width),
    ):
        for _ in range(count):
            features.append(generate_river(
                rng, radius, terrain=terrain, width=width,
                feature_type=ftype, id_=fid,
            ))
            fid += 1

    for _ in range(num_lakes):
        features.append(generate_lake(
            rng, radius, terrain=terrain,
            mean_radius=20.0 + rng.random() * 20.0,
            feature_type="lake", id_=fid,
        ))
        fid += 1

    for _ in range(num_ponds):
        features.append(generate_lake(
            rng, radius, terrain=terrain,
            mean_radius=5.0 + rng.random() * 5.0, irregularity=0.5,
            feature_type="pond", id_=fid,
        ))
        fid += 1

    for _ in range(num_watersheds):
        features.append(generate_lake(
            rng, radius, terrain=terrain,
            mean_radius=40.0 + rng.random() * 30.0, irregularity=0.5,
            feature_type="watershed", id_=fid, requires_bridge=False,
        ))
        fid += 1

    return features


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _seg_intersect(p1, p2, p3, p4):
    """
    Intersection of segment p1-p2 with segment p3-p4, if any.
    Returns (t, point) where t in [0, 1] is the parametric position of the
    intersection along p1-p2 (so callers can sort/split by it), or None if
    the segments don't cross (parallel/collinear counts as no crossing --
    a river running exactly along a road isn't a "crossing").
    """
    x1, y1 = p1; x2, y2 = p2; x3, y3 = p3; x4, y4 = p4
    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(d) < 1e-12:
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / d
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t, (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def _point_in_polygon(pt, poly):
    """Standard ray-casting point-in-polygon test."""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_at_y = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_at_y:
                inside = not inside
    return inside


def _linear_crossings(a, b, feature):
    """
    Where segment a-b crosses a linear water feature's centerline.
    Returns a list of (t0, t1) intervals (in a-b's parametric space) wide
    enough for a bridge to span the water's full width at that crossing,
    accounting for the crossing angle -- a road that crosses a river
    nearly parallel to its bank needs a much longer bridge than one that
    crosses it square-on.
    """
    path = feature["path"]
    width = feature.get("width", 6.0)
    abx, aby = b[0] - a[0], b[1] - a[1]
    road_len = math.hypot(abx, aby)
    if road_len < 1e-9:
        return []
    intervals = []
    for i in range(len(path) - 1):
        p3, p4 = path[i], path[i + 1]
        hit = _seg_intersect(a, b, p3, p4)
        if hit is None:
            continue
        t, _pt = hit
        wdx, wdy = p4[0] - p3[0], p4[1] - p3[1]
        wlen = math.hypot(wdx, wdy)
        if wlen < 1e-9:
            continue
        # sine of the angle between the road and the water centerline;
        # clamped away from 0 so a near-parallel crossing gets a long but
        # finite span instead of blowing up
        sin_angle = max(abs(abx * wdy - aby * wdx) / (road_len * wlen), 0.15)
        span = width / sin_angle
        half_t = (span / 2.0) / road_len
        intervals.append((max(0.0, t - half_t), min(1.0, t + half_t)))
    return intervals


def _polygon_crossings(a, b, feature):
    """
    Where segment a-b passes through an areal water feature's polygon.
    Returns a list of (t0, t1) intervals -- the parts of a-b that lie
    inside the polygon. Handles the segment starting and/or ending inside
    the polygon (odd number of boundary crossings) by clamping to that
    end of the segment.
    """
    poly = feature["polygon"]
    ts = []
    n = len(poly)
    for i in range(n):
        p3, p4 = poly[i], poly[(i + 1) % n]
        hit = _seg_intersect(a, b, p3, p4)
        if hit is not None:
            ts.append(round(hit[0], 9))
    if not ts:
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if _point_in_polygon(mid, poly):
            return [(0.0, 1.0)]
        return []

    ts = sorted(set(ts))
    if _point_in_polygon(a, poly):
        ts = [0.0] + ts
    if len(ts) % 2 == 1:
        ts = ts + [1.0]

    return [(ts[i], ts[i + 1]) for i in range(0, len(ts), 2)]


def find_road_water_crossings(a, b, water_features):
    """
    All (t0, t1, feature) crossing intervals for segment a-b against every
    bridge-requiring water feature. `water_features` entries without
    "requires_bridge" truthy are ignored entirely (e.g. a watershed
    boundary that isn't itself open water).
    """
    hits = []
    for feat in water_features:
        if not feat.get("requires_bridge", True):
            continue
        if "path" in feat:
            for t0, t1 in _linear_crossings(a, b, feat):
                hits.append((t0, t1, feat))
        elif "polygon" in feat:
            for t0, t1 in _polygon_crossings(a, b, feat):
                hits.append((t0, t1, feat))
    return hits


def _merge_crossing_intervals(intervals):
    """Merges overlapping/touching (t0, t1, feature) crossings, keeping
    the first feature reference for the merged span (used only for
    metadata on the resulting bridge segment)."""
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda iv: iv[0])
    merged = [list(intervals[0])]
    for t0, t1, feat in intervals[1:]:
        last = merged[-1]
        if t0 <= last[1] + 1e-6:
            last[1] = max(last[1], t1)
        else:
            merged.append([t0, t1, feat])
    return merged


# ---------------------------------------------------------------------------
# Bridge insertion
# ---------------------------------------------------------------------------

def insert_bridges(roads, water_features, margin=1.5):
    """
    Splits every road segment that crosses a water feature into up to
    three pieces: (approach, bridge, approach). The middle piece is
    tagged "bridge": True plus metadata identifying which water feature
    it crosses and how long the span is, so city_builder.py can render an
    actual bridge deck there instead of a road ribbon running into a
    river. Roads that don't cross any water are returned unchanged.

    `margin` extends each bridge past the water's edge by this many
    meters on both sides (a real bridge's abutments sit back from the
    bank, not flush with the waterline) before re-merging, so two
    crossings close together end up as one continuous bridge instead of
    a sliver of "road" sitting between two river banks.

    Segment dicts are copied (not mutated in place), and any extra keys
    already on a road entry (e.g. "role") are preserved on every piece.
    """
    if not water_features:
        return list(roads)

    result = []
    bridge_id = 0
    for road in roads:
        a = tuple(road["start"])
        b = tuple(road["end"])
        road_len = math.hypot(b[0] - a[0], b[1] - a[1])
        crossings = find_road_water_crossings(a, b, water_features)
        if not crossings or road_len < 1e-6:
            result.append(road)
            continue

        margin_t = margin / road_len
        padded = [
            (max(0.0, t0 - margin_t), min(1.0, t1 + margin_t), feat)
            for t0, t1, feat in crossings
        ]
        spans = _merge_crossing_intervals(padded)

        def _point_at(t):
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

        prev_t = 0.0
        for t0, t1, feat in spans:
            if t0 > prev_t + 1e-6:
                p0, p1 = _point_at(prev_t), _point_at(t0)
                seg = dict(road)
                seg["start"] = [round(p0[0], 4), round(p0[1], 4)]
                seg["end"] = [round(p1[0], 4), round(p1[1], 4)]
                result.append(seg)

            p0, p1 = _point_at(t0), _point_at(t1)
            bridge_id += 1
            seg = dict(road)
            seg["start"] = [round(p0[0], 4), round(p0[1], 4)]
            seg["end"] = [round(p1[0], 4), round(p1[1], 4)]
            seg["bridge"] = True
            seg["bridge_id"] = bridge_id
            seg["water_feature_id"] = feat.get("id")
            seg["water_feature_type"] = feat.get("type")
            seg["bridge_length"] = round(
                math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 3
            )
            result.append(seg)
            prev_t = t1

        if prev_t < 1.0 - 1e-6:
            p0, p1 = _point_at(prev_t), b
            seg = dict(road)
            seg["start"] = [round(p0[0], 4), round(p0[1], 4)]
            seg["end"] = [round(p1[0], 4), round(p1[1], 4)]
            result.append(seg)

    return result
