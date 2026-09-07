"""Pure-Python tests for floorplate room partitioning."""
import math

from pro.rooms import (
    partition_polygon,
    _point_in_convex,
    _polygon_area,
    _inset_convex,
    _clip_polygon,
)


def _rect(w=10.0, d=12.0, origin=(0.0, 0.0)):
    x, y = origin
    return [(x, y), (x + w, y), (x + w, y + d), (x, y + d)]


def _polys_overlap(a, b, eps=1e-4):
    clipped = _clip_polygon(a, b)
    return _polygon_area(clipped) > eps


def test_empty_and_tiny_input():
    assert partition_polygon([])["rooms"] == []
    out = partition_polygon(_rect(1.0, 1.0), min_span=2.0, max_span=0.5)
    assert len(out["rooms"]) == 1
    assert out["walls"] == []


def test_rooms_and_walls_stay_inside():
    poly = _rect(10, 12)
    inset = _inset_convex(poly, 0.18)
    out = partition_polygon(poly, thickness=0.12, margin=0.18, min_span=2.0, max_span=4.5, seed=1)
    assert out["rooms"]
    for item in out["rooms"] + out["walls"]:
        for corner in item["polygon"]:
            assert _point_in_convex(tuple(corner), inset, eps=0.05), (corner, item)


def test_rooms_do_not_overlap_each_other():
    out = partition_polygon(_rect(10, 12), thickness=0.12, min_span=2.0, max_span=4.5, seed=2)
    rooms = out["rooms"]
    assert len(rooms) >= 2
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            assert not _polys_overlap(a["polygon"], b["polygon"]), (i, a, b)


def test_wall_thickness_matches_request():
    thickness = 0.12
    out = partition_polygon(_rect(10, 12), thickness=thickness, min_span=2.0, max_span=4.5, seed=3)
    assert out["walls"]
    for w in out["walls"]:
        assert abs(w["thickness"] - thickness) < 0.03, w


def test_area_conservation_within_one_percent():
    poly = _rect(10, 12)
    margin = 0.18
    inset = _inset_convex(poly, margin)
    target = _polygon_area(inset)
    out = partition_polygon(poly, thickness=0.12, margin=margin, min_span=2.0, max_span=4.5, seed=4)
    got = sum(r["area"] for r in out["rooms"]) + sum(_polygon_area(w["polygon"]) for w in out["walls"])
    assert abs(got - target) / target < 0.01, (got, target)


def test_rectangle_in_rectangles_out():
    out = partition_polygon(_rect(10, 12), thickness=0.12, min_span=2.0, max_span=5.0, seed=5)
    for item in out["rooms"] + out["walls"]:
        assert len(item["polygon"]) == 4
        p = item["polygon"]
        e1 = (p[1][0] - p[0][0], p[1][1] - p[0][1])
        e2 = (p[2][0] - p[1][0], p[2][1] - p[1][1])
        assert e1[0] * e2[1] - e1[1] * e2[0] > 0


def test_same_seed_reproducible():
    kwargs = dict(thickness=0.12, min_span=2.0, max_span=4.5)
    a = partition_polygon(_rect(10, 12), seed=42, **kwargs)
    b = partition_polygon(_rect(10, 12), seed=42, **kwargs)
    assert a == b
    c = partition_polygon(_rect(10, 12), seed=7, **kwargs)
    assert a != c


def test_max_span_creates_more_rooms():
    coarse = partition_polygon(_rect(10, 12), thickness=0.12, min_span=2.0, max_span=8.0, seed=1)
    fine = partition_polygon(_rect(10, 12), thickness=0.12, min_span=2.0, max_span=3.5, seed=1)
    assert len(fine["rooms"]) >= len(coarse["rooms"])
    assert len(fine["walls"]) >= len(coarse["walls"])


def test_min_span_prevents_slivers():
    out = partition_polygon(_rect(10, 12), thickness=0.12, min_span=2.4, max_span=3.0, seed=9)
    for r in out["rooms"]:
        assert r["width"] >= 2.4 - 0.05
        assert r["depth"] >= 2.4 - 0.05


def test_corridor_is_through_hall():
    out = partition_polygon(
        _rect(10, 12), thickness=0.12, min_span=2.0, max_span=20.0,
        corridor=1.2, seed=11,
    )
    halls = [r for r in out["rooms"] if abs(r["width"] - 1.2) < 0.08]
    assert len(halls) >= 1, out["rooms"]
    hall = max(halls, key=lambda r: r["depth"])
    assert hall["depth"] > 10.0
    assert len(out["walls"]) >= 2
    assert len(out["rooms"]) >= 3  # hall + two sides


def test_corridor_skipped_when_too_narrow():
    out = partition_polygon(
        _rect(1.3, 8), thickness=0.12, min_span=0.4, max_span=20.0,
        corridor=1.2, seed=1,
    )
    # 1.3 < 1.2 + 2*0.12, so corridor cannot fit with walls
    halls = [r for r in out["rooms"] if abs(r["width"] - 1.2) < 0.08]
    assert halls == []


def test_partition_operator_records_kwargs():
    from pro.base import context
    from pro.op_partition import Partition

    class _DummyParent:
        def addChildOperator(self, o):
            pass

        def removeChildOperators(self, n):
            pass

    context.operator = _DummyParent()
    dummy_wall = object()
    dummy_room = object()
    p = Partition(wall=dummy_wall, room=dummy_room, thickness=0.2, corridor=1.1, seed=3, margin=0.18)
    assert p.thickness == 0.2
    assert p.corridor == 1.1
    assert p.seed == 3
    assert p.margin == 0.18
    assert p.wall is dummy_wall
    assert p.room is dummy_room


def test_rotated_rectangle_still_partitions():
    ang = math.radians(35)
    c, s = math.cos(ang), math.sin(ang)
    def rot(p):
        return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)
    poly = [rot(p) for p in _rect(10, 12)]
    out = partition_polygon(poly, thickness=0.12, min_span=2.0, max_span=4.5, seed=3)
    assert out["rooms"] and out["walls"]
    for w in out["walls"]:
        assert abs(w["thickness"] - 0.12) < 0.04
