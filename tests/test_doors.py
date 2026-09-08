"""Pure-Python tests for door hinge records."""
import math

from pro.doors import door_record, game_sidecar
from pro.openings import Opening


def test_door_record_hinge_on_left_jamb():
    poly = [(0.0, 0.0), (5.0, 0.0), (5.0, 0.18), (0.0, 0.18)]
    o = Opening(offset=1.0, width=1.0, height=2.1)
    rec = door_record(poly, z0=0.0, opening=o, kind="street", plot_id=7)
    assert rec["kind"] == "street"
    assert rec["plot_id"] == 7
    assert abs(rec["width"] - 1.0) < 1e-9
    assert abs(rec["height"] - 2.1) < 1e-9
    assert abs(rec["location"][2]) < 1e-9
    assert abs(math.hypot(rec["forward"][0], rec["forward"][1]) - 1.0) < 1e-6


def test_game_sidecar_names_doors():
    doors = [{"location": [0, 0, 0], "width": 0.9, "height": 2.1, "plot_id": 3}]
    doc = game_sidecar(doors, [{"plot_id": 3}], [0, 0, 0.1, 0], lights_ref="city.lights.json")
    assert doc["units"] == "m"
    assert doc["doors"][0]["name"] == "Door_3_0"
    assert doc["lights_ref"] == "city.lights.json"
