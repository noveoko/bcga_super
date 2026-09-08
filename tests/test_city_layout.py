"""
Tests for pro/city/layout.py -- the organic Voronoi-based city layout
engine. Pure Python (numpy/scipy), no Blender dependency. Skipped
automatically if numpy/scipy aren't installed (they're not a dependency
of the core pro/ package -- see pro/city/layout.py's module docstring).
"""
import math

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

from pro.city.layout import (
    generate_city_layout,
    generate_polish_town_layout,
    ROAD_WIDTHS,
    DEFAULT_ROAD_WIDTH,
)


def _segments_intersect(p1, p2, p3, p4):
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)


def _is_simple_polygon(poly):
    n = len(poly)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i or j == (i + 1) % n or (j + 1) % n == i:
                continue
            if _segments_intersect(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                return False
    return True


def test_all_blocks_are_valid_polygons():
    layout = generate_city_layout(numBlocks=50, radius=150, seed=1)
    assert len(layout["blocks"]) > 0
    for b in layout["blocks"]:
        assert len(b["polygon"]) >= 3
        assert b["area"] > 0


def test_no_self_intersecting_blocks_across_many_seeds():
    for seed in range(15):
        layout = generate_city_layout(numBlocks=40, radius=150, seed=seed)
        for b in layout["blocks"]:
            poly = [tuple(p) for p in b["polygon"]]
            assert _is_simple_polygon(poly), (seed, b["id"])


def test_density_decreases_with_distance_from_center():
    layout = generate_city_layout(numBlocks=60, radius=200, centerBias=1.6, seed=42)
    near = [b for b in layout["blocks"] if b["distance_from_center"] < 50]
    far = [b for b in layout["blocks"] if b["distance_from_center"] > 150]
    assert near and far
    avgNear = sum(b["density"] for b in near) / len(near)
    avgFar = sum(b["density"] for b in far) / len(far)
    assert avgNear > avgFar


def test_blocks_near_center_are_smaller():
    layout = generate_city_layout(numBlocks=60, radius=200, centerBias=1.6, seed=42)
    near = [b for b in layout["blocks"] if b["distance_from_center"] < 50]
    far = [b for b in layout["blocks"] if b["distance_from_center"] > 150]
    assert near and far
    avgAreaNear = sum(b["area"] for b in near) / len(near)
    avgAreaFar = sum(b["area"] for b in far) / len(far)
    assert avgAreaNear < avgAreaFar


def test_all_vertices_within_city_boundary():
    layout = generate_city_layout(numBlocks=50, radius=200, seed=3)
    for b in layout["blocks"]:
        for x, y in b["polygon"]:
            assert math.hypot(x, y) <= 200 + 1.0


def test_same_seed_is_reproducible():
    a = generate_city_layout(numBlocks=40, radius=150, seed=42)
    b = generate_city_layout(numBlocks=40, radius=150, seed=42)
    assert a["blocks"] == b["blocks"]


def test_different_seed_differs():
    a = generate_city_layout(numBlocks=40, radius=150, seed=42)
    b = generate_city_layout(numBlocks=40, radius=150, seed=7)
    assert a["blocks"] != b["blocks"]


def test_roads_have_hierarchy_and_are_within_boundary():
    layout = generate_city_layout(numBlocks=40, radius=150, seed=1)
    assert len(layout["roads"]) > 0
    hierarchies = {r["hierarchy"] for r in layout["roads"]}
    assert hierarchies <= {"primary", "secondary"}
    for r in layout["roads"]:
        for pt in (r["start"], r["end"]):
            assert math.hypot(*pt) <= 150 + 1.0


def _dist_point_to_segment(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    if L2 < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
    return math.hypot(p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy))


@pytest.mark.parametrize("seed", [1927, 1, 42])
def test_polish_town_houses_never_overlap_a_road(seed):
    """
    city_builder.py draws each road as a ribbon of real width, centered on
    the same line the block/plot geometry treats as the road (see
    layout.py's _block_edge_setbacks docstring). No plot's street-facing
    wall should sit closer to a road's centerline than that road's own
    half-width -- otherwise the road ribbon would be drawn straight
    through the front of the house.
    """
    layout = generate_polish_town_layout(seed=seed)
    roads = layout["roads"]
    for plot in layout["plots"]:
        a, b = plot["polygon"][0], plot["polygon"][1]
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        for r in roads:
            ra, rb = r["start"], r["end"]
            width = ROAD_WIDTHS.get(r["hierarchy"], DEFAULT_ROAD_WIDTH)
            clearance = _dist_point_to_segment(mid, ra, rb)
            assert clearance >= width / 2.0 - 0.05, (
                plot.get("id"), r["hierarchy"], clearance, width / 2.0
            )


def test_too_few_blocks_raises_clear_error():
    with pytest.raises(ValueError):
        generate_city_layout(numBlocks=2, radius=100)
