"""
Integration test for the full city-building pipeline: pro/city/layout.py
(pure Python) + city_builder.py (real Blender). Skipped if numpy/scipy
and/or Blender aren't available.
"""
import json
import os
import re
import subprocess

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

pytestmark = pytest.mark.integration


def _run_city_builder(blender_executable, repo_root, layoutPath, ruleFile, outputPath):
    cmd = [
        blender_executable, "--background", "--factory-startup", "--python",
        os.path.join(repo_root, "city_builder.py"), "--",
        "--layout", str(layoutPath), "--rule", ruleFile, "--output", str(outputPath),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def test_full_city_pipeline(blender_executable, repo_root, tmp_path):
    if not blender_executable:
        pytest.skip("no `blender` executable found")

    from pro.city.layout import generate_city_layout, save_city_layout

    layoutPath = tmp_path / "layout.json"
    layout = generate_city_layout(numBlocks=20, radius=100, seed=1)
    save_city_layout(layout, str(layoutPath))
    assert len(layout["blocks"]) > 0

    outputPath = tmp_path / "city.blend"
    ruleFile = os.path.join(repo_root, "examples", "city_building.py")
    proc = _run_city_builder(blender_executable, repo_root, layoutPath, ruleFile, outputPath)
    assert proc.returncode == 0, proc.stderr
    assert outputPath.exists()
    assert "Built" in proc.stdout
    assert "road curve object" in proc.stdout

    # Every block should succeed -- examples/city_building.py's own
    # try/except around hip_roof() already absorbs the one known source of
    # per-block failure (the straight-skeleton roof algorithm isn't 100%
    # robust on every possible irregular polygon), and the underlying
    # bpro engine bugs that used to make *most* blocks fail regardless of
    # rule-file content (a missing `import bmesh` in bpro/__init__.py, and
    # RawValue/Modifier/Param.execute() not accepting the ctx argument
    # every caller passes -- see tests/test_execute_ctx_signature.py) are
    # now fixed. A failure here means something regressed.
    m = re.search(r"Built (\d+) block\(s\), (\d+) failed", proc.stdout)
    assert m
    built, failed = int(m.group(1)), int(m.group(2))
    assert built == len(layout["blocks"])
    assert failed == 0


def test_polish_town_pipeline(blender_executable, repo_root, tmp_path):
    if not blender_executable:
        pytest.skip("no `blender` executable found")

    from pro.city.layout import generate_polish_town_layout, save_city_layout

    layoutPath = tmp_path / "polish_layout.json"
    layout = generate_polish_town_layout(seed=1927)
    save_city_layout(layout, str(layoutPath))
    assert len(layout["plots"]) > 0

    outputPath = tmp_path / "polish_town.blend"
    ruleFile = os.path.join(repo_root, "examples", "polish_town_1927.py")
    proc = _run_city_builder(blender_executable, repo_root, layoutPath, ruleFile, outputPath)
    assert proc.returncode == 0, proc.stderr
    assert outputPath.exists()

    m = re.search(r"Built (\d+) house\(s\), (\d+) failed", proc.stdout)
    assert m
    built, failed = int(m.group(1)), int(m.group(2))
    assert built == len(layout["plots"])
    assert failed == 0
