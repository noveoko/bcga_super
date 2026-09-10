"""
Tests for pro/city/water.py -- water-feature generation and the
road/water bridging logic -- plus its integration into
generate_city_layout / generate_polish_town_layout.
"""
import math
import random

import pytest

from pro.city.water import (
    _seg_intersect,
    _point_in_polygon,
    find_road_water_crossings,
    insert_bridges,
    generate_river,
    generate_lake,
    generate_water_bodies,
)

pytest.importorskip("numpy")
pytest.importorskip("scipy")

from pro.city.layout import generate_city_layout, generate_polish_town_layout


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

def test_seg_intersect_finds_crossing():
    hit = _seg_intersect((-1, 0), (1, 0), (0, -1), (0, 1))
    assert hit is not None
    t, pt = hit
    assert math.isclose(t, 0.5)
    assert math.isclose(pt[0], 0.0, abs_tol=1e-9)
    assert math.isclose(pt[1], 0.0, abs_tol=1e-9)


def test_seg_intersect_parallel_lines_no_crossing():
    assert _seg_intersect((0, 0), (1, 0), (0, 1), (1, 1)) is None


def test_seg_intersect_segments_that_dont_reach_each_other():
    # would cross if extended into full lines, but not within either segment
    assert _seg_intersect((-1, 0), (-0.5, 0), (0, -1), (0, 1)) is None


def test_point_in_polygon():
    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert _point_in_polygon((5, 5), square) is True
    assert _point_in_polygon((15, 5), square) is False


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def test_generate_river_stays_within_boundary_and_has_metadata():
    rng = random.Random(3)
    river = generate_river(rng, radius=100.0, width=5.0, id_=0)
    assert river["type"] == "river"
    assert river["width"] == 5.0
    assert river["requires_bridge"] is True
    assert len(river["path"]) >= 2
    for x, y in river["path"]:
        assert math.hypot(x, y) <= 100.0 + 1.0


def test_generate_river_is_reproducible_with_same_seed():
    r1 = generate_river(random.Random(7), radius=120.0)
    r2 = generate_river(random.Random(7), radius=120.0)
    assert r1["path"] == r2["path"]


def test_generate_lake_polygon_is_closed_shape_around_center():
    rng = random.Random(5)
    lake = generate_lake(rng, radius=100.0, center=(0, 0), mean_radius=20.0, num_verts=10)
    assert lake["type"] == "lake"
    assert len(lake["polygon"]) == 10
    for x, y in lake["polygon"]:
        assert 5.0 < math.hypot(x, y) < 35.0  # roughly mean_radius +/- irregularity


def test_generate_water_bodies_assigns_sequential_ids_and_types():
    rng = random.Random(9)
    features = generate_water_bodies(
        rng, radius=150.0, num_rivers=1, num_lakes=1, num_ponds=1, num_watersheds=1
    )
    types = [f["type"] for f in features]
    assert types == ["river", "lake", "pond", "watershed"]
    assert [f["id"] for f in features] == [0, 1, 2, 3]
    # a watershed is a catchment boundary, not open water -- no bridge needed
    assert features[-1]["requires_bridge"] is False


# ---------------------------------------------------------------------------
# Crossing detection / bridge insertion
# ---------------------------------------------------------------------------

def test_road_crossing_river_gets_split_into_three_with_middle_as_bridge():
    road = {"start": [-10, 0], "end": [10, 0], "hierarchy": "local"}
    river = {
        "id": 0, "type": "river", "path": [[0, -20], [0, 20]],
        "width": 4.0, "requires_bridge": True,
    }
    result = insert_bridges([road], [river], margin=1.0)
    assert len(result) == 3
    approach1, bridge, approach2 = result
    assert bridge["bridge"] is True
    assert bridge["water_feature_type"] == "river"
    assert bridge["hierarchy"] == "local"  # preserved from the original road
    assert not approach1.get("bridge")
    assert not approach2.get("bridge")
    # bridge spans at least the river's width
    assert bridge["bridge_length"] >= river["width"]
    # approaches + bridge reconstruct the original road exactly
    assert approach1["start"] == road["start"]
    assert approach2["end"] == road["end"]


def test_road_not_crossing_water_is_unchanged():
    road = {"start": [-10, 100], "end": [10, 100], "hierarchy": "local"}
    river = {
        "id": 0, "type": "river", "path": [[0, -20], [0, 20]],
        "width": 4.0, "requires_bridge": True,
    }
    result = insert_bridges([road], [river])
    assert result == [road]


def test_road_crossing_lake_polygon_gets_bridged():
    road = {"start": [-50, 0], "end": [50, 0], "hierarchy": "secondary"}
    lake = {
        "id": 1, "type": "lake",
        "polygon": [[-10, -10], [10, -10], [10, 10], [-10, 10]],
        "requires_bridge": True,
    }
    result = insert_bridges([road], [lake], margin=0.0)
    bridges = [r for r in result if r.get("bridge")]
    assert len(bridges) == 1
    b = bridges[0]
    assert b["water_feature_type"] == "lake"
    assert math.isclose(b["bridge_length"], 20.0, rel_tol=0.05)


def test_watershed_does_not_require_a_bridge_by_default():
    road = {"start": [-50, 0], "end": [50, 0], "hierarchy": "secondary"}
    watershed = {
        "id": 2, "type": "watershed",
        "polygon": [[-10, -10], [10, -10], [10, 10], [-10, 10]],
        "requires_bridge": False,
    }
    result = insert_bridges([road], [watershed])
    assert result == [road]


def test_find_road_water_crossings_ignores_non_bridge_features():
    a, b = (-50, 0), (50, 0)
    watershed = {
        "id": 2, "type": "watershed",
        "polygon": [[-10, -10], [10, -10], [10, 10], [-10, 10]],
        "requires_bridge": False,
    }
    assert find_road_water_crossings(a, b, [watershed]) == []


def test_adjacent_crossings_merge_into_one_bridge():
    # two touching water rectangles right next to each other along the road
    road = {"start": [-50, 0], "end": [50, 0], "hierarchy": "local"}
    left = {
        "id": 0, "type": "pond",
        "polygon": [[-10, -10], [0, -10], [0, 10], [-10, 10]],
        "requires_bridge": True,
    }
    right = {
        "id": 1, "type": "pond",
        "polygon": [[0, -10], [10, -10], [10, 10], [0, 10]],
        "requires_bridge": True,
    }
    result = insert_bridges([road], [left, right], margin=0.0)
    bridges = [r for r in result if r.get("bridge")]
    assert len(bridges) == 1
    assert math.isclose(bridges[0]["bridge_length"], 20.0, rel_tol=0.05)


# ---------------------------------------------------------------------------
# Integration with generate_city_layout / generate_polish_town_layout
# ---------------------------------------------------------------------------

def test_generate_city_layout_without_water_has_empty_water_list():
    layout = generate_city_layout(numBlocks=30, radius=120, seed=1)
    assert layout["water"] == []
    assert all(not r.get("bridge") for r in layout["roads"])


def test_generate_city_layout_with_water_produces_bridges():
    layout = generate_city_layout(
        numBlocks=40, radius=150, seed=1,
        generate_water=True, num_rivers=1,
    )
    assert len(layout["water"]) == 1
    assert layout["water"][0]["type"] == "river"
    assert any(r.get("bridge") for r in layout["roads"])


def test_generate_city_layout_water_is_reproducible():
    a = generate_city_layout(numBlocks=40, radius=150, seed=42, generate_water=True, num_rivers=1, num_lakes=1)
    b = generate_city_layout(numBlocks=40, radius=150, seed=42, generate_water=True, num_rivers=1, num_lakes=1)
    assert a["water"] == b["water"]
    assert a["roads"] == b["roads"]


def test_explicit_water_bodies_are_used_as_is():
    river = {
        "id": 0, "type": "river", "path": [[0, -200], [0, 200]],
        "width": 8.0, "requires_bridge": True,
    }
    layout = generate_city_layout(numBlocks=30, radius=120, seed=2, water_bodies=[river])
    assert layout["water"] == [river]
    assert any(r.get("bridge") for r in layout["roads"])


def test_polish_town_layout_bridges_rynek_ring_roads_too():
    river = {
        "id": 0, "type": "river", "path": [[0, -200], [0, 200]],
        "width": 10.0, "requires_bridge": True,
    }
    layout = generate_polish_town_layout(seed=1927, water_bodies=[river])
    # the rynek square's own cobbled ring roads should be bridged where
    # the river cuts through the square, not just the Voronoi streets
    bridged_near_square = [
        r for r in layout["roads"]
        if r.get("bridge") and r["hierarchy"] == "primary"
    ]
    assert bridged_near_square, "expected at least one bridged primary/rynek-ring road"


def test_all_bridge_segments_have_positive_length():
    layout = generate_city_layout(
        numBlocks=50, radius=180, seed=11,
        generate_water=True, num_rivers=1, num_streams=1, num_lakes=1, num_ponds=1,
    )
    bridges = [r for r in layout["roads"] if r.get("bridge")]
    assert bridges
    for b in bridges:
        assert b["bridge_length"] > 0
        dx = b["end"][0] - b["start"][0]
        dy = b["end"][1] - b["start"][1]
        assert math.hypot(dx, dy) > 0
