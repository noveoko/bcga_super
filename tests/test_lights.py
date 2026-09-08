"""Pure-Python tests for ceiling light placement."""
from pro.lights import place_ceiling_lights, lights_sidecar


def _room(cx, cy, w=4.0, d=4.0, role="room"):
    x0, y0 = cx - w / 2.0, cy - d / 2.0
    return {
        "polygon": [(x0, y0), (x0 + w, y0), (x0 + w, y0 + d), (x0, y0 + d)],
        "centroid": [cx, cy],
        "area": w * d,
        "width": w,
        "depth": d,
        "role": role,
    }


def test_empty_rooms_yield_no_lights():
    assert place_ceiling_lights([], 0.0, 3.0, seed=1) == []


def test_skips_tiny_rooms():
    tiny = _room(0, 0, w=1.0, d=1.0)
    assert place_ceiling_lights([tiny], 0.0, 3.0, seed=1) == []


def test_z_is_under_the_ceiling():
    rooms = [_room(i * 5.0, 0.0) for i in range(4)]
    lights = place_ceiling_lights(rooms, z_floor=4.6, height=3.0, drop=0.22, seed=2)
    assert lights
    for L in lights:
        assert abs(L["location"][2] - (4.6 + 3.0 - 0.22)) < 1e-9


def test_seed_is_stable():
    rooms = [_room(i * 5.0, 0.0) for i in range(6)]
    a = place_ceiling_lights(rooms, 0.0, 3.0, seed=42)
    b = place_ceiling_lights(rooms, 0.0, 3.0, seed=42)
    assert [L["location"] for L in a] == [L["location"] for L in b]


def test_qualifying_floor_gets_at_least_one_light():
    rooms = [_room(i * 5.0, 0.0) for i in range(5)]
    lights = place_ceiling_lights(rooms, 0.0, 3.0, seed=7)
    assert len(lights) >= 1


def test_large_room_gets_a_second_lamp():
    big = _room(0, 0, w=5.0, d=5.0)  # 25 m²
    lights = place_ceiling_lights([big], 0.0, 3.0, seed=1, density_range=(1.0, 1.0))
    assert len(lights) == 2


def test_sidecar_names_and_units():
    rooms = [_room(0, 0, w=4, d=4)]
    placed = place_ceiling_lights(rooms, 0.0, 3.0, seed=1, density_range=(1.0, 1.0))
    doc = lights_sidecar(placed)
    assert doc["units"] == "m"
    assert doc["axis"] == "blender_z_up"
    assert doc["lights"][0]["type"] == "Point"
    assert doc["lights"][0]["name"].startswith("LIGHT_")
    assert doc["lights"][0]["intensity_unit"] == "candela"
