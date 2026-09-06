"""Pure-Python tests for street-edge parceling."""
import math

from pro.city.parcels import parcel_block, _point_in_convex, _rects_overlap


def _square(s=40.0):
    h = s / 2.0
    return [(-h, -h), (h, -h), (h, h), (-h, h)]


def test_plots_are_rectangles_inside_block():
    rng = __import__("random").Random(1)
    block = _square(50)
    plots = parcel_block(block, density=0.7, rng=rng)
    assert len(plots) >= 8
    for p in plots:
        assert len(p["polygon"]) == 4
        assert 6.0 <= p["width"] <= 16.0
        assert 5.0 <= p["depth"] <= 18.0
        for corner in p["polygon"]:
            assert _point_in_convex(tuple(corner), block, eps=0.2)


def test_plots_do_not_overlap():
    rng = __import__("random").Random(2)
    plots = parcel_block(_square(60), density=0.5, rng=rng)
    assert len(plots) >= 6
    for i, a in enumerate(plots):
        for b in plots[i + 1:]:
            assert not _rects_overlap(a["polygon"], b["polygon"], gap=0.05), (i, a, b)


def test_higher_density_more_plots():
    dense = parcel_block(_square(50), density=1.0, rng=__import__("random").Random(3))
    sparse = parcel_block(_square(50), density=0.0, rng=__import__("random").Random(3))
    assert len(dense) >= len(sparse)


def test_tiny_block_yields_nothing_or_few():
    plots = parcel_block(_square(8), density=0.5, rng=__import__("random").Random(0))
    assert len(plots) <= 2


def test_street_edge_is_first_and_ccw():
    plots = parcel_block(_square(40), density=0.8, rng=__import__("random").Random(4))
    assert plots
    p = plots[0]["polygon"]
    # CCW: cross of first two edges >= 0
    e1 = (p[1][0] - p[0][0], p[1][1] - p[0][1])
    e2 = (p[2][0] - p[1][0], p[2][1] - p[1][1])
    assert e1[0] * e2[1] - e1[1] * e2[0] > 0
    # first edge is on the block boundary (y == -20 for south side, etc.)
    block = _square(40)
    on_boundary = 0
    for plot in plots:
        a, b = plot["polygon"][0], plot["polygon"][1]
        for i in range(4):
            s, t = block[i], block[(i + 1) % 4]
            # both endpoints near the infinite line of that edge
            if abs(_dist_point_to_segment(a, s, t)) < 0.2 and abs(_dist_point_to_segment(b, s, t)) < 0.2:
                on_boundary += 1
                break
    assert on_boundary == len(plots)


def _dist_point_to_segment(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    if L2 < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
    return math.hypot(p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy))
