"""Pure tests for generated building-rule pool + layout annotation."""
import json
import os

from pro.city.building_rules import (
    annotate_layout_rules,
    ensure_building_rules,
    next_building_rule_path,
    save_rule_to_pool,
)


def test_ensure_building_rules_creates_twenty(tmp_path):
    rules_dir = str(tmp_path / "rules")
    paths = ensure_building_rules(rules_dir, count=20, force=True)
    assert len(paths) == 20
    assert all(os.path.isfile(p) for p in paths)
    text = open(paths[0], encoding="utf-8").read()
    assert "from pro import *" in text
    assert "@rule" in text
    assert "_PRESET" in text


def test_ensure_building_rules_idempotent(tmp_path):
    rules_dir = str(tmp_path / "rules")
    first = ensure_building_rules(rules_dir, count=20, force=True)
    mtime = os.path.getmtime(first[0])
    second = ensure_building_rules(rules_dir, count=20, force=False)
    assert second == first
    assert os.path.getmtime(first[0]) == mtime


def test_annotate_layout_rules_on_blocks():
    layout = {
        "seed": 7,
        "blocks": [
            {"id": 0, "role": "plaza"},
            {"id": 1, "role": "kamienica"},
            {"id": 2},
        ],
    }
    rules = ["/abs/building_00.py", "/abs/building_01.py"]
    annotate_layout_rules(layout, rules, seed=7)
    assert "rule" not in layout["blocks"][0]
    assert layout["blocks"][1]["rule"] in rules
    assert layout["blocks"][2]["rule"] in rules


def test_annotate_layout_rules_prefers_plots():
    layout = {
        "seed": 1,
        "blocks": [{"id": 0}],
        "plots": [{"id": 10}, {"id": 11}],
    }
    rules = ["/r/a.py", "/r/b.py", "/r/c.py"]
    annotate_layout_rules(layout, rules, seed=1)
    assert layout["plots"][0]["rule"] in rules
    assert layout["plots"][1]["rule"] in rules
    assert "rule" not in layout["blocks"][0]


def test_annotate_layout_rules_reproducible():
    layout_a = {"seed": 99, "blocks": [{"id": i} for i in range(8)]}
    layout_b = json.loads(json.dumps(layout_a))
    rules = ["/r/%02d.py" % i for i in range(5)]
    annotate_layout_rules(layout_a, rules, seed=99)
    annotate_layout_rules(layout_b, rules, seed=99)
    assert [b["rule"] for b in layout_a["blocks"]] == [b["rule"] for b in layout_b["blocks"]]


def test_next_building_rule_path_starts_at_20(tmp_path):
    rules_dir = str(tmp_path / "rules")
    ensure_building_rules(rules_dir, count=20, force=True)
    path = next_building_rule_path(rules_dir, start_at=20)
    assert path.endswith("building_20.py")


def test_save_rule_to_pool_writes_content(tmp_path):
    rules_dir = str(tmp_path / "rules")
    ensure_building_rules(rules_dir, count=20, force=True)
    src = "from pro import *\n\n@rule\ndef Begin():\n    extrude(3)\n"
    path = save_rule_to_pool(src, rules_dir=rules_dir, start_at=20)
    assert os.path.basename(path) == "building_20.py"
    assert "def Begin" in open(path, encoding="utf-8").read()
    path2 = save_rule_to_pool(src, rules_dir=rules_dir, start_at=20)
    assert os.path.basename(path2) == "building_21.py"
