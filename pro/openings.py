"""
Interior openings on 2-D wall segments.

No bpy. Opening metadata lives on wall records from partition_polygon;
openings() in bpro turns those into piers + a lintel without CSG.
"""
from dataclasses import asdict, dataclass
import math


@dataclass
class Opening:
    offset: float
    width: float = 0.9
    height: float = 2.1
    sill_height: float = 0.0

    def to_dict(self):
        return asdict(self)


def opening_from(obj):
    if isinstance(obj, Opening):
        return obj
    return Opening(
        offset=float(obj["offset"]),
        width=float(obj.get("width", 0.9)),
        height=float(obj.get("height", 2.1)),
        sill_height=float(obj.get("sill_height", 0.0)),
    )


class WallSegment:
    def __init__(self, start, end, thickness=0.12):
        self.start = (float(start[0]), float(start[1]))
        self.end = (float(end[0]), float(end[1]))
        self.thickness = float(thickness)
        self.openings = []

    @property
    def length(self):
        return math.hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])

    def add_opening(self, width=0.9, height=2.1, offset=None, sill_height=0.0):
        width = float(width)
        if offset is None:
            offset = max(0.0, (self.length - width) / 2.0)
        self.openings.append(
            Opening(
                offset=float(offset),
                width=width,
                height=float(height),
                sill_height=float(sill_height),
            )
        )
        return self


def decompose_spans(length, openings, min_pier=0.0):
    """
    Split [0, length] into solid/gap intervals.
    Later openings that overlap an earlier one are skipped (no merge).
    """
    length = float(length)
    prepared = []
    for raw in openings or []:
        o = opening_from(raw)
        if o.width <= 1e-9:
            continue
        start = max(0.0, o.offset)
        end = min(length, o.offset + o.width)
        if end - start <= 1e-9:
            continue
        prepared.append((start, end, o))
    prepared.sort(key=lambda t: t[0])

    kept = []
    cursor = 0.0
    for start, end, o in prepared:
        if start < cursor - 1e-9:
            continue
        kept.append((start, end, o))
        cursor = end

    spans = []
    t = 0.0
    for start, end, o in kept:
        if start > t + 1e-9:
            spans.append({"kind": "solid", "start": t, "end": start, "length": start - t})
        spans.append({
            "kind": "gap",
            "start": start,
            "end": end,
            "length": end - start,
            "opening": o,
        })
        t = end
    if t < length - 1e-9:
        spans.append({"kind": "solid", "start": t, "end": length, "length": length - t})
    if not spans:
        spans.append({"kind": "solid", "start": 0.0, "end": length, "length": length})
    return spans


def place_centered_openings(
    walls,
    width=0.9,
    height=2.1,
    sill_height=0.0,
    min_pier=0.25,
):
    """Stamp one centered door on every wall long enough to fit it."""
    width = float(width)
    need = width + 2.0 * float(min_pier)
    for wall in walls:
        if wall.get("openings"):
            continue
        if wall["length"] >= need:
            offset = (wall["length"] - width) / 2.0
            wall["openings"] = [
                Opening(
                    offset=offset,
                    width=width,
                    height=float(height),
                    sill_height=float(sill_height),
                ).to_dict()
            ]
        else:
            wall["openings"] = []
    return walls


def _wall_axis(wall):
    from .rooms import _longest_edge_axis, _span_along, _centroid

    poly = wall["polygon"]
    _length, edgeDir, _mid = _longest_edge_axis(poly)
    perp = (-edgeDir[1], edgeDir[0])
    lo, hi = _span_along(poly, edgeDir)
    c = wall.get("centroid") or _centroid(poly)
    return edgeDir, perp, lo, hi, c


def rooms_on_wall_sides(wall, rooms, probe=None):
    """
    Sample along the wall and see which rooms sit on each long face.
    Returns (plus_ids, minus_ids).
    """
    from .rooms import _add, _dot, _mul, _point_in_convex

    edgeDir, perp, lo, hi, c = _wall_axis(wall)
    thick = float(wall.get("thickness") or 0.12)
    if probe is None:
        probe = thick / 2.0 + 0.08
    n = max(3, int(float(wall["length"]) / 0.4) + 1)
    c_s = _dot(c, edgeDir)
    plus, minus = set(), set()
    for k in range(n + 1):
        t = lo + (hi - lo) * (k / n)
        base = _add(c, _mul(edgeDir, t - c_s))
        p_plus = _add(base, _mul(perp, probe))
        p_minus = _add(base, _mul(perp, -probe))
        for i, room in enumerate(rooms):
            rpoly = room["polygon"]
            if _point_in_convex(tuple(p_plus), rpoly, eps=0.05):
                plus.add(i)
            if _point_in_convex(tuple(p_minus), rpoly, eps=0.05):
                minus.add(i)
    return list(plus), list(minus)


def _overlap_on_wall(wall, room_a, room_b):
    from .rooms import _span_along

    edgeDir, _perp, lo_w, hi_w, _c = _wall_axis(wall)
    lo_a, hi_a = _span_along(room_a["polygon"], edgeDir)
    lo_b, hi_b = _span_along(room_b["polygon"], edgeDir)
    lo = max(lo_w, lo_a, lo_b)
    hi = min(hi_w, hi_a, hi_b)
    return max(0.0, hi - lo), lo, hi, lo_w


def _exit_room_ids(rooms):
    halls = [i for i, r in enumerate(rooms) if r.get("role") == "hall"]
    if halls:
        return halls
    if not rooms:
        return []
    return [max(range(len(rooms)), key=lambda i: rooms[i].get("area") or 0.0)]


def _opening_fits(wall, overlap, width, min_pier):
    return overlap + 1e-9 >= float(width) + 2.0 * float(min_pier)


def _offset_for_overlap(lo, hi, lo_w, width, min_pier, wall_length):
    mid = 0.5 * (lo + hi)
    offset = mid - lo_w - width / 2.0
    lo_ok = float(min_pier)
    hi_ok = float(wall_length) - float(width) - float(min_pier)
    if hi_ok < lo_ok:
        return (float(wall_length) - float(width)) / 2.0
    return max(lo_ok, min(hi_ok, offset))


def _openings_overlap(existing, offset, width):
    for o in existing:
        a0, a1 = o["offset"], o["offset"] + o["width"]
        b0, b1 = offset, offset + width
        if b0 < a1 - 1e-9 and a0 < b1 - 1e-9:
            return True
    return False


def adjacency_candidates(rooms, walls, width=0.9, min_pier=0.25):
    """
    Shared-wall edges of the room graph that can take a door.
    Each item: (room_a, room_b, wall_index, overlap, offset).
    """
    width = float(width)
    min_pier = float(min_pier)
    found = []
    for w_i, wall in enumerate(walls):
        plus, minus = rooms_on_wall_sides(wall, rooms)
        if not plus or not minus:
            continue
        for a in plus:
            for b in minus:
                overlap, lo, hi, lo_w = _overlap_on_wall(wall, rooms[a], rooms[b])
                if not _opening_fits(wall, overlap, width, min_pier):
                    continue
                offset = _offset_for_overlap(lo, hi, lo_w, width, min_pier, wall["length"])
                found.append((a, b, w_i, overlap, offset))
    return found


def connectivity_graph(rooms, walls):
    """Undirected graph: room id -> list of (other_id, wall_index). Only walls with openings."""
    graph = {i: [] for i in range(len(rooms))}
    for w_i, wall in enumerate(walls):
        if not wall.get("openings"):
            continue
        plus, minus = rooms_on_wall_sides(wall, rooms)
        for a in plus:
            for b in minus:
                graph[a].append((b, w_i))
                graph[b].append((a, w_i))
    return graph


def reachable_room_ids(rooms, walls, starts=None):
    if starts is None:
        starts = _exit_room_ids(rooms)
    graph = connectivity_graph(rooms, walls)
    seen = set(starts)
    queue = list(starts)
    while queue:
        i = queue.pop(0)
        for j, _w in graph.get(i, []):
            if j not in seen:
                seen.add(j)
                queue.append(j)
    return seen


def dead_end_rooms(rooms, walls, starts=None):
    seen = reachable_room_ids(rooms, walls, starts)
    return [i for i in range(len(rooms)) if i not in seen]


def place_openings_from_adjacency(
    rooms,
    walls,
    width=0.9,
    height=2.1,
    sill_height=0.0,
    min_pier=0.25,
):
    """
    One door per room-pair on a spanning tree rooted at the hall (or the
    largest room). Extra shared walls are left solid. Unreachable rooms
    get a second-pass door onto the nearest reached neighbor if a fitting
    wall exists.
    """
    width = float(width)
    height = float(height)
    sill_height = float(sill_height)
    min_pier = float(min_pier)
    for wall in walls:
        wall.setdefault("openings", [])

    if not rooms or not walls:
        return walls

    candidates = adjacency_candidates(rooms, walls, width=width, min_pier=min_pier)
    exits = _exit_room_ids(rooms)
    attractor = rooms[exits[0]]["centroid"]

    def wall_score(w_i, overlap):
        wc = walls[w_i]["centroid"]
        dx = wc[0] - attractor[0]
        dy = wc[1] - attractor[1]
        return (dx * dx + dy * dy, -overlap)

    reached = set(exits)
    used_pairs = set()

    def add_door(w_i, offset):
        wall = walls[w_i]
        if _openings_overlap(wall["openings"], offset, width):
            return False
        wall["openings"].append(
            Opening(
                offset=offset,
                width=width,
                height=height,
                sill_height=sill_height,
            ).to_dict()
        )
        return True

    def grow():
        best = None
        for a, b, w_i, overlap, offset in candidates:
            if (a in reached) == (b in reached):
                continue
            pair = frozenset((a, b))
            if pair in used_pairs:
                continue
            score = wall_score(w_i, overlap)
            if best is None or score < best[0]:
                best = (score, a, b, w_i, offset)
        if best is None:
            return False
        _score, a, b, w_i, offset = best
        if not add_door(w_i, offset):
            used_pairs.add(frozenset((a, b)))
            return True
        used_pairs.add(frozenset((a, b)))
        reached.add(a if a not in reached else b)
        return True

    while len(reached) < len(rooms):
        if not grow():
            break
    return walls


def slice_wall_polygon(poly, t0, t1):
    """
    Clip a wall polygon to the interval [t0, t1] meters along its longest edge.
    """
    from .rooms import (
        _add, _clip_half, _centroid, _dot, _longest_edge_axis, _mul, _span_along, _valid_poly,
    )

    if t1 <= t0 + 1e-9:
        return []
    _length, edgeDir, _mid = _longest_edge_axis(poly)
    lo, _hi = _span_along(poly, edgeDir)
    c = _centroid(poly)
    c_s = _dot(c, edgeDir)

    def point_at(s):
        return _add(c, _mul(edgeDir, (lo + s) - c_s))

    piece = _clip_half(poly, point_at(t0), edgeDir)
    piece = _clip_half(piece, point_at(t1), (-edgeDir[0], -edgeDir[1]))
    if not _valid_poly(piece):
        return []
    return piece
