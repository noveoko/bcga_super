"""Pure-Python tests for interior opening metadata and span splits.

pro/openings.py is the bpy-free model: dataclasses + pure helpers, no Blender.
"""
from pro.openings import (
    Opening,
    WallSegment,
    adjacency_candidates,
    connectivity_graph,
    dead_end_rooms,
    decompose_spans,
    opening_from,
    place_centered_openings,
    place_openings_from_adjacency,
    reachable_room_ids,
    rooms_on_wall_sides,
    slice_wall_polygon,
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


def test_overlapping_openings():
    """Later openings that overlap an earlier one are skipped (no merge)."""
    spans = decompose_spans(
        6.0,
        [
            Opening(offset=0.5, width=1.0),
            Opening(offset=1.2, width=1.0),  # overlaps first → skipped
            Opening(offset=3.0, width=0.8),  # clear of first → kept
        ],
    )
    gaps = [s for s in spans if s["kind"] == "gap"]
    assert len(gaps) == 2
    assert abs(gaps[0]["start"] - 0.5) < 1e-12
    assert abs(gaps[0]["length"] - 1.0) < 1e-12
    assert abs(gaps[1]["start"] - 3.0) < 1e-12
    assert abs(gaps[1]["length"] - 0.8) < 1e-12
    assert abs(sum(s["length"] for s in spans) - 6.0) < 1e-12


def test_opening_clipped_to_wall():
    """Openings overhanging [0, length] are clamped before span split."""
    spans = decompose_spans(
        4.0,
        [
            Opening(offset=-0.5, width=1.0),  # clamps to [0, 0.5]
            Opening(offset=3.5, width=1.5),   # clamps to [3.5, 4.0]
        ],
    )
    gaps = [s for s in spans if s["kind"] == "gap"]
    assert len(gaps) == 2
    assert abs(gaps[0]["start"] - 0.0) < 1e-12
    assert abs(gaps[0]["length"] - 0.5) < 1e-12
    assert abs(gaps[1]["start"] - 3.5) < 1e-12
    assert abs(gaps[1]["length"] - 0.5) < 1e-12
    assert abs(sum(s["length"] for s in spans) - 4.0) < 1e-12


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


def test_door_requires_minimum_piers():
    """Centered doors need length >= width + 2*min_pier (exact fit ok; short fails)."""
    width, min_pier = 0.9, 0.25
    need = width + 2.0 * min_pier

    exact = [{"length": need, "polygon": []}]
    place_centered_openings(exact, width=width, min_pier=min_pier)
    assert len(exact[0]["openings"]) == 1
    assert abs(exact[0]["openings"][0]["offset"] - min_pier) < 1e-12

    too_short = [{"length": need - 1e-6, "polygon": []}]
    place_centered_openings(too_short, width=width, min_pier=min_pier)
    assert too_short[0]["openings"] == []

    # Adjacency uses shared overlap vs width+2*min_pier (polygon-derived).
    rooms, walls = _two_rooms_one_wall()
    assert adjacency_candidates(rooms, walls, width=width, min_pier=min_pier)
    # Shared overlap is ~4.0m; door 3.6 + 2*0.25 piers needs 4.1 → no candidate.
    assert adjacency_candidates(rooms, walls, width=3.6, min_pier=0.25) == []


def test_place_centered_skips_wall_that_already_has_openings():
    walls = [{
        "length": 4.0,
        "polygon": [],
        "openings": [{"offset": 0.1, "width": 0.9, "height": 2.1, "sill_height": 0.0}],
    }]
    place_centered_openings(walls, width=0.9, min_pier=0.25)
    assert len(walls[0]["openings"]) == 1
    assert abs(walls[0]["openings"][0]["offset"] - 0.1) < 1e-12


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


def test_adjacent_rooms_get_door():
    """Shared wall between two rooms gets exactly one door with pier margins."""
    rooms, walls = _two_rooms_one_wall()
    width, min_pier = 0.9, 0.25
    place_openings_from_adjacency(rooms, walls, width=width, min_pier=min_pier)
    o = walls[0]["openings"][0]
    assert abs(o["width"] - width) < 1e-12
    assert o["offset"] >= min_pier - 1e-9
    assert o["offset"] + o["width"] <= walls[0]["length"] - min_pier + 1e-9
    assert reachable_room_ids(rooms, walls) == {0, 1}


def test_adjacency_candidates_lists_shared_wall():
    rooms, walls = _two_rooms_one_wall()
    found = adjacency_candidates(rooms, walls, width=0.9, min_pier=0.25)
    assert len(found) >= 1
    a, b, w_i, overlap, offset = found[0]
    assert frozenset((a, b)) == frozenset((0, 1))
    assert w_i == 0
    assert overlap + 1e-9 >= 0.9 + 2.0 * 0.25
    assert 0.0 <= offset <= walls[0]["length"] - 0.9


def test_connectivity_graph_links_rooms_with_openings_only():
    rooms, walls = _two_rooms_one_wall()
    before = connectivity_graph(rooms, walls)
    assert before[0] == []
    assert before[1] == []

    place_openings_from_adjacency(rooms, walls, width=0.9, min_pier=0.25)
    after = connectivity_graph(rooms, walls)
    assert any(j == 1 for j, _w in after[0])
    assert any(j == 0 for j, _w in after[1])


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


def test_opening_from_dict_and_dataclass():
    o = Opening(offset=1.0, width=0.8, height=2.0, sill_height=0.1)
    assert opening_from(o) is o
    from_dict = opening_from(
        {"offset": 1.0, "width": 0.8, "height": 2.0, "sill_height": 0.1}
    )
    assert from_dict.offset == 1.0
    assert from_dict.width == 0.8
    assert from_dict.height == 2.0
    assert from_dict.sill_height == 0.1
    defaults = opening_from({"offset": 0.5})
    assert defaults.width == 0.9
    assert defaults.height == 2.1
    assert defaults.sill_height == 0.0


def test_opening_to_dict_roundtrip_fields():
    o = Opening(offset=1.25, width=0.95, height=2.15, sill_height=0.05)
    d = o.to_dict()
    assert d == {
        "offset": 1.25,
        "width": 0.95,
        "height": 2.15,
        "sill_height": 0.05,
    }
    assert opening_from(d).to_dict() == d


def test_rooms_on_wall_sides_detects_left_and_right():
    rooms, walls = _two_rooms_one_wall()
    plus, minus = rooms_on_wall_sides(walls[0], rooms)
    assert set(plus) | set(minus) == {0, 1}
    assert set(plus).isdisjoint(set(minus))


def test_slice_wall_polygon_clips_along_longest_edge():
    # Axis-aligned wall strip 0.12 thick, 4m along Y (longest edge)
    poly = [(0.0, 0.0), (0.12, 0.0), (0.12, 4.0), (0.0, 4.0)]
    piece = slice_wall_polygon(poly, 1.0, 2.5)
    assert piece
    ys = [p[1] for p in piece]
    assert min(ys) >= 1.0 - 1e-6
    assert max(ys) <= 2.5 + 1e-6
    assert slice_wall_polygon(poly, 2.0, 2.0) == []
