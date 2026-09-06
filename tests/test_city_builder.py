"""
Integration test for the full city-building pipeline: pro/city/layout.py
(pure Python) + city_builder.py (real Blender). Skipped if numpy/scipy
and/or Blender aren't available.
"""
import json
import os
import subprocess

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

pytestmark = pytest.mark.integration


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
    cmd = [
        blender_executable, "--background", "--factory-startup", "--python",
        os.path.join(repo_root, "city_builder.py"), "--",
        "--layout", str(layoutPath), "--rule", ruleFile, "--output", str(outputPath),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr
    assert outputPath.exists()
    assert "Built" in proc.stdout
    assert "road curve object" in proc.stdout

    # at least some blocks should have succeeded (the underlying
    # straight-skeleton roof algorithm isn't 100% robust on every possible
    # irregular polygon shape -- see city_builder.py's per-block try/except
    # and examples/city_building.py's own defensive containment -- but the
    # large majority of a normal layout should still succeed)
    import re
    m = re.search(r"Built (\d+) block\(s\), (\d+) failed", proc.stdout)
    assert m
    built, failed = int(m.group(1)), int(m.group(2))
    assert built > 0
    assert built >= failed  # more successes than failures, as a sanity floor
