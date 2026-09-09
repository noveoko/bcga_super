"""
Pure-Python tests for streamlit_app/dsl_generator.py. None of this touches
Gemini, Streamlit, or bpy -- it exercises the footprint math and the static
validator that runs on whatever the model comes back with.
"""
import math
import re

import pytest

from dsl_generator import (
    RuleFileError,
    build_prompt,
    extract_code_block,
    footprint_bbox_size_m,
    pin_footprint_dimensions,
    pixel_polygon_to_meters,
    validate_rule_file,
)


# ---------------------------------------------------------------------------
# pixel_polygon_to_meters / footprint_bbox_size_m
# ---------------------------------------------------------------------------

def test_pixel_polygon_to_meters_scales_and_centers_a_square():
    # a 100x100 px square, top-left corner at (200, 300)
    px = [(200, 300), (300, 300), (300, 400), (200, 400)]
    m = pixel_polygon_to_meters(px, target_longest_side_m=10.0)
    w, h = footprint_bbox_size_m(m)
    assert abs(w - 10.0) < 1e-9
    assert abs(h - 10.0) < 1e-9
    # centered on its own centroid
    cx = sum(p[0] for p in m) / len(m)
    cy = sum(p[1] for p in m) / len(m)
    assert abs(cx) < 1e-9
    assert abs(cy) < 1e-9


def test_pixel_polygon_to_meters_flips_y_and_scales_by_longest_side():
    # a 2:1 rectangle, 200px wide x 100px tall
    px = [(0, 0), (200, 0), (200, 100), (0, 100)]
    m = pixel_polygon_to_meters(px, target_longest_side_m=20.0)
    w, h = footprint_bbox_size_m(m)
    assert abs(w - 20.0) < 1e-9   # longest side (width) pinned to target
    assert abs(h - 10.0) < 1e-9   # short side scaled by the same factor

    # y should be flipped: the pixel with the smallest py (topmost on
    # screen) must end up with the largest metric y (matches the
    # up-is-+y convention used by pro/city block/plot polygons).
    top_px = [p for p in px if p[1] == 0][0]
    top_idx = px.index(top_px)
    bottom_px = [p for p in px if p[1] == 100][0]
    bottom_idx = px.index(bottom_px)
    assert m[top_idx][1] > m[bottom_idx][1]


def test_pixel_polygon_to_meters_rejects_degenerate_input():
    with pytest.raises(ValueError):
        pixel_polygon_to_meters([(0, 0), (1, 1)], target_longest_side_m=5.0)  # only 2 points
    with pytest.raises(ValueError):
        pixel_polygon_to_meters([(5, 5), (5, 5), (5, 5)], target_longest_side_m=5.0)  # zero extent


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_pins_footprint_and_includes_full_contract():
    contract = "=== FAKE CONTRACT TEXT FOR TESTING ==="
    footprint = [(-4.0, -3.0), (4.0, -3.0), (4.0, 3.0), (-4.0, 3.0)]
    prompt = build_prompt(contract, footprint, storeys=2, role="barn",
                           material="wood", phase="damaged", notes="leaning east wall")
    assert "BUILDING_WIDTH = 8.00 and BUILDING_DEPTH = 6.00" in prompt
    assert "GROUND TRUTH" in prompt
    assert "2 storeys" in prompt
    assert "barn" in prompt
    assert "wood" in prompt
    assert "leaning east wall" in prompt
    assert contract in prompt  # the fixed operator contract must be passed through verbatim


def test_build_prompt_omits_optional_fields_when_not_given():
    contract = "CONTRACT"
    footprint = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    prompt = build_prompt(contract, footprint)
    assert "storeys" not in prompt
    assert "Building type/role" not in prompt
    assert "Construction phase" not in prompt


# ---------------------------------------------------------------------------
# extract_code_block / pin_footprint_dimensions
# ---------------------------------------------------------------------------

def test_extract_code_block_strips_markdown_fence():
    text = "Here you go:\n```python\nfrom pro import *\nx = 1\n```\nHope that helps!"
    assert extract_code_block(text) == "from pro import *\nx = 1\n"


def test_extract_code_block_handles_no_fence():
    text = "from pro import *\nx = 1"
    assert extract_code_block(text) == "from pro import *\nx = 1\n"


def test_pin_footprint_dimensions_rewrites_constants():
    source = "BUILDING_WIDTH = 12.0\nBUILDING_DEPTH = 7.5\nWALL_H = 4.2\n"
    fixed, ok = pin_footprint_dimensions(source, 9.123, 5.5)
    assert ok is True
    assert "BUILDING_WIDTH = 9.123" in fixed
    assert "BUILDING_DEPTH = 5.500" in fixed
    assert "WALL_H = 4.2" in fixed  # untouched


def test_pin_footprint_dimensions_noop_when_constants_absent():
    source = "WALL_H = 4.2\n"
    fixed, ok = pin_footprint_dimensions(source, 9.0, 5.0)
    assert ok is False
    assert fixed == source


# ---------------------------------------------------------------------------
# validate_rule_file -- this is the part that matters most: it has to catch
# the exact failure modes IMAGE_TO_RULE_PROMPT.md was written to prevent.
# ---------------------------------------------------------------------------

VALID_MINIMAL = """\
from pro import *

BUILDING_WIDTH = 10.0
BUILDING_DEPTH = 6.0

@rule
def Begin():
    rectangle(BUILDING_WIDTH, BUILDING_DEPTH, MainMass())
    delete()

@rule
def MainMass():
    color("#efe8dc")
    extrude(4.2, top >> Roof())

@rule
def Roof():
    hip_roof(35, 0.4, face >> RoofFace())

@rule
def RoofFace():
    color("#4a5c48")
"""


def test_validate_accepts_the_canonical_skeleton():
    # the "Canonical single-mass skeleton" from IMAGE_TO_RULE_PROMPT.md,
    # used verbatim so a regression here means real generations would break.
    # It references Basement()/FloorSlabs() (HAS_BASEMENT = True), which are
    # defined in the doc's separate "Floors, cellar, stairs" section -- pull
    # both blocks in, same as a real generated file would need to.
    from pathlib import Path
    doc = Path(__file__).resolve().parent.parent / "examples" / "IMAGE_TO_RULE_PROMPT.md"
    text = doc.read_text(encoding="utf-8")
    skeleton = re.search(r"### Canonical single-mass skeleton\n\n```python\n(.*?)```", text, re.S)
    floors = re.search(r"### Floors, cellar, stairs.*?\n\n```python\n(.*?)```", text, re.S)
    assert skeleton and floors, "couldn't find the expected code blocks in IMAGE_TO_RULE_PROMPT.md"
    combined = skeleton.group(1) + "\n" + floors.group(1)
    assert validate_rule_file(combined) is True


def test_validate_accepts_minimal_valid_file():
    assert validate_rule_file(VALID_MINIMAL) is True


def test_validate_rejects_syntax_errors():
    with pytest.raises(RuleFileError) as exc:
        validate_rule_file("def Begin(:\n    pass")
    assert any("not valid Python" in p for p in exc.value.problems)


def test_validate_rejects_missing_import():
    bad = VALID_MINIMAL.replace("from pro import *\n", "")
    with pytest.raises(RuleFileError) as exc:
        validate_rule_file(bad)
    assert any("from pro import" in p for p in exc.value.problems)


def test_validate_rejects_missing_begin():
    bad = VALID_MINIMAL.replace("def Begin():", "def Start():").replace(
        "def MainMass():", "def MainMass():\n    pass  # unreachable now, but that's fine for this test"
    )
    with pytest.raises(RuleFileError) as exc:
        validate_rule_file(bad)
    assert any("Begin" in p for p in exc.value.problems)


@pytest.mark.parametrize("banned_call", [
    "spawn_at(0, 0, 0)",
    "primitive_cube(1, 1, 1)",
    "comp('front', Wall())",
    "split_v(0.5, Wall())",
    "repeat_h(flt(2.4) >> Bay())",
    "roof_hip(30, 0.4)",
    "set_material('Brick')",
])
def test_validate_rejects_every_hallucinated_operator_from_the_prompt_doc(banned_call):
    bad = VALID_MINIMAL + "\n@rule\ndef Bad():\n    %s\n" % banned_call
    with pytest.raises(RuleFileError) as exc:
        validate_rule_file(bad)
    assert any("does not have" in p for p in exc.value.problems)


def test_validate_rejects_undefined_rule_reference():
    # MainMass() calls a rule that sounds plausible but was never defined
    # -- the single most common way a model invents an API without using a
    # banned function name at all.
    bad = VALID_MINIMAL.replace(
        "def MainMass():\n    color(\"#efe8dc\")",
        "def MainMass():\n    color(\"#efe8dc\")\n    NeoclassicalCornice()",
    )
    with pytest.raises(RuleFileError) as exc:
        validate_rule_file(bad)
    assert any("NeoclassicalCornice" in p for p in exc.value.problems)


def test_validate_rejects_bpy_import():
    bad = "import bpy\n" + VALID_MINIMAL
    with pytest.raises(RuleFileError) as exc:
        validate_rule_file(bad)
    assert any("bpy" in p for p in exc.value.problems)


def test_validate_reports_multiple_problems_at_once():
    bad = "def Begin():\n    spawn_at(0, 0, 0)\n    GhostRule()\n"
    with pytest.raises(RuleFileError) as exc:
        validate_rule_file(bad)
    # missing import, missing @rule on Begin, banned call, undefined rule --
    # all four should be reported together, not just the first one found
    assert len(exc.value.problems) >= 3
