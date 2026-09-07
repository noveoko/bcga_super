"""Pure-Python tests for interior opening metadata and span splits."""
from pro.openings import (
    Opening,
    WallSegment,
    dead_end_rooms,
    decompose_spans,
    place_centered_openings,
    place_openings_from_adjacency,
    reachable_room_ids,
)
from pro.rooms import partition_polygon


def test_wall_segment_add_opening_stores_fields():
    seg = WallSegment(start=(0, 0), end=(4.2, 0))
    assert abs(seg.length - 4.2) < 1e-12
    seg.add_opening(width=0.9, height=2.1, offset=1.2, sill_height=0.0)
    assert len(seg.openings) == 1
    o = seg.openings[0]
    assert o.offset == 1.2
    assert o.width == 0.9
    assert o.height == 2.1
    assert o.sill_height == 0.0


def test_add_opening_none_offset_centers():
    seg = WallSegment((0, 0), (4.0, 0))
    seg.add_opening(width=0.9)
    assert abs(seg.openings[0].offset - 1.55) < 1e-12


def test_decompose_spans_one_door():
    spans = decompose_spans(4.0, [Opening(offset=1.2, width=0.9)])
    kinds = [s["kind"] for s in spans]
    assert kinds == ["solid", "gap", "solid"]
    assert abs(spans[0]["length"] - 1.2) < 1e-12
    assert abs(spans[1]["length"] - 0.9) < 1e-12
    assert abs(spans[2]["length"] - 1.9) < 1e-12
    assert abs(sum(s["length"] for s in spans) - 4.0) < 1e-12


def test_decompose_spans_two_openings_sorted():
    spans = decompose_spans(
        8.0,
        [Opening(offset=5.0, width=0.9), Opening(offset=1.0, width=0.9)],
    )
    gaps = [s for s in spans if s["kind"] == "gap"]
    assert len(gaps) == 2
    assert abs(gaps[0]["start"] - 1.0) < 1e-12
    assert abs(gaps[1]["start"] - 5.0) < 1e-12
    assert abs(sum(s["length"] for s in spans) - 8.0) < 1e-12


def test_overlapping_opening_is_skipped():
    spans = decompose_spans(
        4.0,
        [Opening(offset=1.0, width=1.2), Opening(offset=1.5, width=0.9)],
    )
    gaps = [s for s in spans if s["kind"] == "gap"]
    assert len(gaps) == 1
    assert abs(gaps[0]["start"] - 1.0) < 1e-12
    assert abs(gaps[0]["length"] - 1.2) < 1e-12


def test_short_wall_gets_no_centered_door():
    walls = [{"length": 1.0, "polygon": []}]
    place_centered_openings(walls, width=0.9, min_pier=0.25)
    assert walls[0]["openings"] == []


def test_long_wall_gets_centered_door():
    walls = [{"length": 4.0, "polygon": []}]
    place_centered_openings(walls, width=0.9, height=2.1, min_pier=0.25)
    assert len(walls[0]["openings"]) == 1
    o = walls[0]["openings"][0]
    assert abs(o["offset"] - 1.55) < 1e-12
    assert o["width"] == 0.9


def _two_rooms_one_wall():
    rooms = [
        {
            "id": 0, "role": "hall", "area": 16.0, "centroid": [2.0, 2.0],
            "polygon": [[0, 0], [3.94, 0], [3.94, 4], [0, 4]],
        },
        {
            "id": 1, "role": "room", "area": 15.0, "centroid": [6.0, 2.0],
            "polygon": [[4.06, 0], [8, 0], [8, 4], [4.06, 4]],
        },
    ]
    walls = [
        {
            "length": 4.0, "thickness": 0.12, "centroid": [4.0, 2.0],
            "polygon": [[3.94, 0], [4.06, 0], [4.06, 4], [3.94, 4]],
            "openings": [],
        }
    ]
    return rooms, walls


def test_adjacency_places_one_door_on_shared_wall():
    rooms, walls = _two_rooms_one_wall()
    place_openings_from_adjacency(rooms, walls, width=0.9, min_pier=0.25)
    assert len(walls[0]["openings"]) == 1
    assert abs(walls[0]["openings"][0]["width"] - 0.9) < 1e-12
    assert dead_end_rooms(rooms, walls) == []


def test_adjacency_picks_one_wall_when_two_share_the_same_pair():
    rooms, walls = _two_rooms_one_wall()
    extra = {
        "length": 2.0, "thickness": 0.12, "centroid": [4.0, 0.5],
        "polygon": [[3.94, 0], [4.06, 0], [4.06, 2], [3.94, 2]],
        "openings": [],
    }
    walls.append(extra)
    place_openings_from_adjacency(rooms, walls, width=0.9, min_pier=0.25)
    n_doors = sum(len(w["openings"]) for w in walls)
    assert n_doors == 1


def test_short_shared_wall_is_not_a_door():
    rooms, walls = _two_rooms_one_wall()
    walls[0]["length"] = 1.0
    walls[0]["polygon"] = [[3.94, 0], [4.06, 0], [4.06, 1], [3.94, 1]]
    place_openings_from_adjacency(rooms, walls, width=0.9, min_pier=0.25)
    assert walls[0]["openings"] == []


def test_partition_polygon_connects_rooms_from_the_hall():
    poly = [(0, 0), (10, 0), (10, 12), (0, 12)]
    out = partition_polygon(
        poly, thickness=0.12, min_span=2.0, max_span=4.5, seed=3,
        corridor=1.2, door_width=0.9,
    )
    halls = [r for r in out["rooms"] if r.get("role") == "hall"]
    assert halls
    n_doors = sum(1 for w in out["walls"] if w.get("openings"))
    assert n_doors >= 1
    assert n_doors <= max(1, len(out["rooms"]) - 1)
    dead = dead_end_rooms(out["rooms"], out["walls"])
    assert dead == [], (dead, n_doors, len(out["rooms"]))


def test_no_corridor_still_connects_via_largest_room():
    poly = [(0, 0), (10, 0), (10, 12), (0, 12)]
    out = partition_polygon(
        poly, thickness=0.12, min_span=2.0, max_span=4.5, seed=7, door_width=0.9,
    )
    assert out["rooms"]
    assert dead_end_rooms(out["rooms"], out["walls"]) == []


def test_reachable_from_hall_covers_every_room():
    poly = [(0, 0), (10, 0), (10, 12), (0, 12)]
    out = partition_polygon(
        poly, thickness=0.12, min_span=2.0, max_span=4.5, seed=1,
        corridor=1.2, door_width=0.9,
    )
    seen = reachable_room_ids(out["rooms"], out["walls"])
    assert seen == set(range(len(out["rooms"])))


def test_partition_polygon_default_has_no_doors():
    poly = [(0, 0), (10, 0), (10, 12), (0, 12)]
    out = partition_polygon(poly, thickness=0.12, min_span=2.0, max_span=4.5, seed=3)
    for w in out["walls"]:
        assert w.get("openings", []) == []


def test_partition_segment_builder():
    from pro.op_partition import partition
    seg = partition.segment(start=(0, 0), end=(4.2, 0))
    seg.add_opening(width=0.9, height=2.1, offset=1.2)
    assert abs(seg.length - 4.2) < 1e-12
    assert seg.openings[0].offset == 1.2


def test_openings_operator_records_height():
    from pro.base import context
    from pro.op_openings import Openings

    class _DummyParent:
        def addChildOperator(self, o):
            pass

        def removeChildOperators(self, n):
            pass

    context.operator = _DummyParent()
    op = Openings(3.27)
    assert abs(op.wall_height - 3.27) < 1e-12
