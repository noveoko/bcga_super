import pytest

from pro.openings import WallSegment


def test_wall_segment_rejects_invalid_opening_values():
    wall = WallSegment((0, 0), (4, 0))

    with pytest.raises(ValueError):
        wall.add_opening(width=0)
    with pytest.raises(ValueError):
        wall.add_opening(width=-1)
    with pytest.raises(ValueError):
        wall.add_opening(width=5)
    with pytest.raises(ValueError):
        wall.add_opening(height=0)
    with pytest.raises(ValueError):
        wall.add_opening(sill_height=-0.1)


def test_wall_segment_centers_opening_by_default():
    wall = WallSegment((0, 0), (4, 0))
    wall.add_opening(width=1)

    assert wall.openings[0].offset == 1.5


def test_wall_segment_rejects_out_of_bounds_offset():
    wall = WallSegment((0, 0), (4, 0))

    with pytest.raises(ValueError):
        wall.add_opening(width=1, offset=4)


def test_wall_segment_rejects_negative_thickness():
    with pytest.raises(ValueError):
        WallSegment((0, 0), (4, 0), thickness=-0.01)
